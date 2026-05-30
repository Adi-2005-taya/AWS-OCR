"""FastAPI web server for DocuSense System

Run with:
    uvicorn src.web:app --reload

Then open: http://localhost:8000
"""

import io
import re
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.auth import (
    COOKIE_NAME,
    _redirect_to_login,
    authenticate_user,
    build_google_auth_url,
    consume_reset_token,
    create_reset_token,
    create_session_token,
    create_user,
    exchange_google_code,
    get_current_user,
    google_is_configured,
    load_users,
    login_or_create_google_user,
    require_auth,
    send_reset_email,
    verify_reset_token,
)

from src.application import OCRApplication
from src.cache import DocumentCache
from src.constants import DocumentStatus
from src.error_handler import ErrorLogger
from src.models import Document, OCRResult
from src.monitoring import HealthChecker, MetricsCollector
from src.ocr_service import OCRServiceInterface, RateLimitedOCRService
from src.retry import IndexingRetryQueue
from src.search_engine import PersistentSearchEngine
from src.status_manager import StatusManager
from src.storage import LocalFileSystemStorage
from src.text_cleaner import TextCleaner
from src.validation import FileTypeValidator

# ---------------------------------------------------------------------------
# Tool paths
# ---------------------------------------------------------------------------
import sys

if sys.platform == "win32":
    _TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _POPPLER   = (
        r"C:\Users\wbadi\AppData\Local\Microsoft\WinGet\Packages"
        r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\poppler-25.07.0\Library\bin"
    )
else:
    _TESSERACT = "/usr/bin/tesseract"
    _POPPLER   = None  # On Linux, pdf2image will automatically find poppler in system PATH


# ---------------------------------------------------------------------------
# Real OCR service with per-page tracking
# ---------------------------------------------------------------------------

class RealFileOCRService(OCRServiceInterface):
    """Extracts real text from PDFs and images using Tesseract + pdfplumber."""

    # ── helpers ──────────────────────────────────────────────────────

    def _clean(self, text: str) -> str:
        """Strip non-ASCII garbage, collapse spaces, drop short lines."""
        # Fast regex-based approach instead of per-character loop
        cleaned = re.sub(r'[^\x00-\x7F\n\t\r ]+', ' ', text)  # non-ASCII → space
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)              # collapse horizontal whitespace
        lines = [l.strip() for l in cleaned.splitlines() if len(l.strip()) >= 3]
        return "\n".join(lines).strip()

    def _tesseract_image(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT
            img = Image.open(io.BytesIO(image_bytes))
            # Downscale massive images — speeds up OCR significantly
            max_dim = 1800
            if max(img.width, img.height) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
            return pytesseract.image_to_string(img, config='--oem 3 --psm 3').strip()
        except Exception:
            return ""

    def _pdf_pages(self, data: bytes):
        """Return list of per-page text strings.

        Priority:
          1. PyMuPDF native text  — instant, zero rasterization for digital PDFs
          2. Parallel Tesseract   — for scanned/image-only PDFs (lower dpi=150)
          3. pdfplumber fallback  — last resort
        """
        # ── 1. PyMuPDF fast native extraction ──────────────────────────
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=data, filetype="pdf")
            pages_text = [page.get_text().strip() for page in doc]
            total = sum(len(p) for p in pages_text)
            if total > 50:  # has meaningful native text
                doc.close()
                return pages_text
            # Image-only PDF — rasterize for Tesseract below
            pix_list = []
            for page in doc:
                pix_list.append(page.get_pixmap(dpi=150))
            doc.close()
            # Convert pixmaps → PIL images and run Tesseract in parallel
            import pytesseract
            from PIL import Image as _PIL_Image
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT

            def _ocr_pix(pix):
                try:
                    img = _PIL_Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    return pytesseract.image_to_string(img, config='--oem 3 --psm 3').strip()
                except Exception:
                    return ""

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(4, len(pix_list) or 1)) as ex:
                return list(ex.map(_ocr_pix, pix_list))
        except Exception:
            pass

        # ── 2. Parallel Tesseract via pdf2image (lower DPI = faster) ───
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            from concurrent.futures import ThreadPoolExecutor
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT
            images = convert_from_bytes(data, dpi=150, poppler_path=_POPPLER)

            def _ocr_img(img):
                try:
                    return pytesseract.image_to_string(img, config='--oem 3 --psm 3').strip()
                except Exception:
                    return ""

            with ThreadPoolExecutor(max_workers=min(4, len(images) or 1)) as ex:
                return list(ex.map(_ocr_img, images))
        except Exception:
            pass

        # ── 3. pdfplumber text-only fallback ───────────────────────────
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
            clean = []
            for pt in pages:
                lines = [l.strip() for l in pt.splitlines()
                         if l.strip() and
                         sum(1 for c in l if ord(c) > 127) / max(len(l), 1) < 0.3]
                clean.append("\n".join(lines))
            return clean
        except Exception:
            return []

    # ── main entry point ─────────────────────────────────────────────

    def extract_text(self, image_data: bytes, document_id) -> OCRResult:
        t0 = time.time()

        if image_data[:4] == b"%PDF":
            raw_pages = self._pdf_pages(image_data)
        else:
            raw_pages = [self._tesseract_image(image_data)]

        # Clean each page
        clean_pages = [self._clean(p) for p in raw_pages]
        full_text   = "\n".join(clean_pages).strip()

        if not full_text or len(full_text) < 10:
            full_text = "document content could not be extracted"

        return OCRResult(
            documentId=document_id,
            rawText=full_text,
            confidence=0.90,
            processingTime=time.time() - t0,
            metadata={
                "engine":     "tesseract+pdfplumber",
                "chars":      len(full_text),
                "page_count": len(clean_pages),
                "pages":      clean_pages,   # ← per-page text stored here
            },
        )

    def get_supported_formats(self):
        return ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_storage    = LocalFileSystemStorage(base_path="./data/storage", encryption_enabled=False)
_ocr        = RateLimitedOCRService(RealFileOCRService())
_engine     = PersistentSearchEngine(index_path="./data/search_index.json")
_status_mgr = StatusManager()
_cache      = DocumentCache()
_error_log  = ErrorLogger()
_retry_q    = IndexingRetryQueue()
_metrics    = MetricsCollector()
_health     = HealthChecker()

_health.register("storage",       lambda: True)
_health.register("search_engine", lambda: True)
_health.register("ocr_service",   lambda: True)

# Restore status for documents already in the persistent index
for _doc_id in list(_engine.documents):
    try:
        _status_mgr.get_status(_doc_id)
    except Exception:
        _dummy = Document(
            id=_doc_id, filename="restored",
            storageUrl=f"storage://{_doc_id}",
            contentType="application/pdf",
            status=DocumentStatus.INDEXED,
        )
        _status_mgr.register(_dummy)
        _status_mgr.transition(_doc_id, DocumentStatus.INDEXED, validate=False)

_app = OCRApplication(
    storage=_storage, ocr_service=_ocr,
    text_cleaner=TextCleaner(), search_engine=_engine,
    status_manager=_status_mgr, document_cache=_cache,
    error_logger=_error_log, retry_queue=_retry_q,
    file_validator=FileTypeValidator(),
)
_app._monitor.start()

# Pending hashes: doc_id -> {file_hash, storage_url}
# Attached to IndexedDocument.metadata after processing completes
_pending_hashes: dict = {}

def _attach_hash_on_index(event):
    """After a document is indexed, attach its file hash and filename to metadata."""
    doc_id_str = str(event.document_id)
    if doc_id_str in _pending_hashes:
        info = _pending_hashes.pop(doc_id_str)
        # Wait briefly for the engine to finish indexing, then patch
        import threading
        def patch():
            import time; time.sleep(0.5)
            doc = _engine.documents.get(event.document_id)
            if doc:
                doc.metadata.update(info)
                _engine._save()
        threading.Thread(target=patch, daemon=True).start()

_status_mgr.register_change_callback(_attach_hash_on_index)

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="DocuSense", version="0.1.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

_HTML_FILE          = Path(__file__).parent / "static" / "index.html"
_ABOUT_FILE         = Path(__file__).parent / "static" / "about.html"
_LOGIN_FILE         = Path(__file__).parent / "static" / "login.html"
_SIGNUP_FILE        = Path(__file__).parent / "static" / "signup.html"
_FORGOT_FILE        = Path(__file__).parent / "static" / "forgot-password.html"
_RESET_FILE         = Path(__file__).parent / "static" / "reset-password.html"

# ---------------------------------------------------------------------------
# Auth exception handler — catches require_auth redirects
# ---------------------------------------------------------------------------

@app.exception_handler(_redirect_to_login)
async def auth_redirect_handler(request: Request, exc: _redirect_to_login):
    return RedirectResponse(url="/login", status_code=303)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/login")
async def auth_login(request: Request,
                     email: str = Form(...),
                     password: str = Form(...)):
    user_id, error = authenticate_user(email, password)
    if error:
        return JSONResponse({"ok": False, "error": error}, status_code=401)
    token = create_session_token(user_id)
    resp  = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=60*60*24*7)
    return resp


@app.post("/auth/signup")
async def auth_signup(request: Request,
                      name: str = Form(...),
                      email: str = Form(...),
                      password: str = Form(...)):
    ok, error = create_user(name, email, password)
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    user_id, _ = authenticate_user(email, password)
    token = create_session_token(user_id)
    resp  = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=60*60*24*7)
    return resp


@app.get("/auth/logout")
def auth_logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.get("/me")
def me(request: Request):
    """Return current user info (name + email + picture) for the header display."""
    user_id = get_current_user(request)
    if not user_id:
        return JSONResponse({"authenticated": False})
    users = load_users()
    u = users.get(user_id, {})
    return {"authenticated": True, "name": u.get("name", user_id),
            "email": u.get("email", user_id), "picture": u.get("picture", "")}


# ---------------------------------------------------------------------------
# Page routes — protected
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user_id: str = Depends(require_auth)):
    return _HTML_FILE.read_text(encoding="utf-8")

@app.get("/about", response_class=HTMLResponse)
def about(request: Request, user_id: str = Depends(require_auth)):
    return _ABOUT_FILE.read_text(encoding="utf-8")

@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    # Already logged in? Go to app
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return _LOGIN_FILE.read_text(encoding="utf-8")

@app.get("/signup", response_class=HTMLResponse)
def signup(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return _SIGNUP_FILE.read_text(encoding="utf-8")

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return _FORGOT_FILE.read_text(encoding="utf-8")

@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    """Validate token early so we can show an error before the form."""
    return _RESET_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Password reset API
# ---------------------------------------------------------------------------

@app.post("/auth/forgot-password")
async def auth_forgot(email: str = Form(...)):
    """
    Always return 200 (don't leak whether email exists).
    Sends reset email if account found.
    """
    import os
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    token = create_reset_token(email)
    if token:
        reset_url = f"{base_url}/reset-password?token={token}"
        ok, err = send_reset_email(email, reset_url)
        if not ok:
            # Return the token in dev mode so user can test without SMTP
            return JSONResponse({"ok": True, "dev_token": token,
                                 "email_error": err})
    return JSONResponse({"ok": True})


@app.post("/auth/reset-password")
async def auth_reset(token: str = Form(...),
                     password: str = Form(...)):
    ok, error = consume_reset_token(token, password)
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True})


@app.get("/auth/verify-reset-token")
def verify_reset(token: str = ""):
    user_id = verify_reset_token(token)
    if not user_id:
        return JSONResponse({"valid": False})
    return JSONResponse({"valid": True})


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@app.get("/auth/google")
def google_auth(request: Request):
    if not google_is_configured():
        return JSONResponse({"error": "Google OAuth not configured"}, status_code=503)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/google/callback"
    url = build_google_auth_url(redirect_uri)
    return RedirectResponse(url=url, status_code=302)


@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "",
                          error: str = ""):
    from src.auth import validate_google_state
    if error or not code:
        return RedirectResponse(url="/login?error=google_denied", status_code=303)
    if not validate_google_state(state):
        return RedirectResponse(url="/login?error=invalid_state", status_code=303)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/google/callback"
    google_info = await exchange_google_code(code, redirect_uri)
    if not google_info or not google_info.get("email"):
        return RedirectResponse(url="/login?error=google_failed", status_code=303)
    user_id = login_or_create_google_user(google_info)
    token   = create_session_token(user_id)
    resp    = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                    max_age=60*60*24*7)
    return resp


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...), user_id: str = Depends(require_auth)):
    import hashlib
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # Duplicate detection — hash the file content
    file_hash = hashlib.sha256(data).hexdigest()
    for doc_id, doc in _engine.documents.items():
        if getattr(doc, "ownerId", None) == user_id and doc.metadata.get("file_hash") == file_hash:
            # Already indexed — return existing document instead of re-processing
            return {
                "document_id": str(doc_id),
                "storage_url": doc.metadata.get("storage_url", f"storage://{doc_id}"),
                "status":      "INDEXED",
                "duplicate":   True,
                "message":     "This file was already uploaded and indexed.",
            }

    try:
        result = _app.upload(data, filename=file.filename, content_type=content_type, owner_id=user_id)
        _metrics.record_upload()
        # Store hash in the engine doc after indexing (done async, so store in a pending map)
        _pending_hashes[str(result.document_id)] = {
            "file_hash":   file_hash,
            "storage_url": result.storage_url,
            "filename":    file.filename or "unknown",
        }
        return {
            "document_id": str(result.document_id),
            "storage_url": result.storage_url,
            "status":      result.status,
            "duplicate":   False,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/status/{document_id}")
def get_status(document_id: str, user_id: str = Depends(require_auth)):
    try:
        uid    = UUID(document_id)
        # Check ownership
        doc = _engine.documents.get(uid)
        if doc and getattr(doc, "ownerId", None) != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        result = _app.get_status(uid)
        return {
            "document_id":  str(result.document_id),
            "status":       result.status,
            "error_details": result.error_details,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

@app.get("/download/{document_id}")
def download_document(document_id: str, user_id: str = Depends(require_auth)):
    try:
        uid = UUID(document_id)
        # Check ownership
        doc = _engine.documents.get(uid)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if getattr(doc, "ownerId", None) != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Download bytes from storage
        file_bytes = _app.storage.download(uid)
        # Determine content type (fallback to octet-stream if metadata is missing)
        content_type = "application/octet-stream"
        filename = "document"
        if getattr(doc, "metadata", None):
            filename = doc.metadata.get("filename", filename)
            content_type = doc.metadata.get("contentType")
            
        if not content_type or content_type == "application/octet-stream":
            import mimetypes
            guessed_type, _ = mimetypes.guess_type(filename)
            content_type = guessed_type or "application/octet-stream"
        
        headers = {
            "Content-Disposition": f'inline; filename="{filename}"'
        }
        
        return Response(content=file_bytes, media_type=content_type, headers=headers)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Search — with page numbers
# ---------------------------------------------------------------------------

@app.get("/search")
def search(query: str, limit: int = 10, user_id: str = Depends(require_auth)):
    try:
        import re as _re

        # ── Phrase search: "exact phrase" in quotes ──
        phrase_match = _re.match(r'^["\'](.+)["\']$', query.strip())
        if phrase_match:
            phrase = phrase_match.group(1).lower()
            results = []
            for doc_id, doc in _engine.documents.items():
                if getattr(doc, "ownerId", None) != user_id:
                    continue
                if phrase in doc.cleanedText.lower():
                    # Find context around the phrase
                    idx = doc.cleanedText.lower().find(phrase)
                    start = max(0, idx - 80)
                    end   = min(len(doc.cleanedText), idx + 160)
                    snippet = ("..." if start > 0 else "") + \
                              doc.cleanedText[start:end].strip() + \
                              ("..." if end < len(doc.cleanedText) else "")

                    pages_found = []
                    raw_pages = doc.metadata.get("pages", [])
                    for i, page_text in enumerate(raw_pages, start=1):
                        if phrase in page_text.lower():
                            pages_found.append(i)

                    try:
                        url = _storage.get_url(doc_id)
                    except Exception:
                        url = f"storage://{doc_id}"

                    results.append({
                        "document_id": str(doc_id),
                        "score":       1.0,
                        "snippet":     snippet,
                        "storage_url": url,
                        "pages_found": pages_found,
                        "match_type":  "phrase",
                    })
                    if len(results) >= limit:
                        break

            return {"query": query, "count": len(results), "results": results,
                    "mode": "phrase"}

        # ── Normal keyword search with whole-word matching ──
        hits = _app.search(query, limit=limit, user_id=user_id)
        q_lower = query.lower()
        results = []

        for h in hits:
            pages_found = []
            context_snippet = h.snippet

            doc = _engine.documents.get(h.document_id)
            if doc:
                if getattr(doc, "ownerId", None) != user_id:
                    continue
                raw_pages = doc.metadata.get("pages", [])
                # Whole-word check: all query words must appear as whole words
                words = _re.findall(r'\b\w+\b', q_lower)
                text_lower = doc.cleanedText.lower()
                all_match = all(
                    bool(_re.search(r'\b' + _re.escape(w) + r'\b', text_lower))
                    for w in words if len(w) >= 3
                )
                if not all_match:
                    continue  # skip partial-word matches

                for i, page_text in enumerate(raw_pages, start=1):
                    if q_lower in page_text.lower():
                        pages_found.append(i)
                    elif any(w in page_text.lower() for w in words if len(w) >= 3):
                        pages_found.append(i)

                idx = text_lower.find(q_lower)
                if idx != -1:
                    start = max(0, idx - 80)
                    end   = min(len(doc.cleanedText), idx + 160)
                    context_snippet = ("..." if start > 0 else "") + \
                                      doc.cleanedText[start:end].strip() + \
                                      ("..." if end < len(doc.cleanedText) else "")
                elif words:
                    # Fallback to the first matched word
                    first_idx = -1
                    for w in words:
                        if len(w) < 3: continue
                        w_idx = text_lower.find(w)
                        if w_idx != -1 and (first_idx == -1 or w_idx < first_idx):
                            first_idx = w_idx
                    if first_idx != -1:
                        start = max(0, first_idx - 80)
                        end   = min(len(doc.cleanedText), first_idx + 160)
                        context_snippet = ("..." if start > 0 else "") + \
                                          doc.cleanedText[start:end].strip() + \
                                          ("..." if end < len(doc.cleanedText) else "")

            results.append({
                "document_id": str(h.document_id),
                "score":       h.score,
                "snippet":     context_snippet,
                "storage_url": h.storage_url,
                "pages_found": pages_found,
                "match_type":  "keyword",
            })

        return {"query": query, "count": len(results), "results": results,
                "mode": "keyword"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@app.delete("/delete/{document_id}")
def delete(document_id: str, user_id: str = Depends(require_auth)):
    try:
        uid    = UUID(document_id)
        doc = _engine.documents.get(uid)
        if doc and getattr(doc, "ownerId", None) != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        result = _app.delete(uid)
        return {
            "document_id":    str(result.document_id),
            "storage_deleted": result.storage_deleted,
            "index_deleted":   result.index_deleted,
            "success":         result.success,
            "error":           result.error,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Health / Metrics / Debug
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    s = _health.check_all()
    return {
        "healthy": s.healthy,
        "checks": [{"name": c.name, "healthy": c.healthy,
                    "message": c.message, "latency_ms": c.latency_ms}
                   for c in s.checks],
    }

@app.get("/metrics")
def metrics():
    m = _metrics.metrics
    return {
        "upload_count":        m.upload_count,
        "processing_success":  m.processing_success_count,
        "processing_failure":  m.processing_failure_count,
        "ocr_calls":           m.ocr_call_count,
        "ocr_success_rate":    round(m.ocr_success_rate, 3),
        "avg_ocr_time_s":      round(m.avg_ocr_processing_time, 3),
        "search_queries":      m.search_query_count,
        "cache_hit_rate":      round(m.cache_hit_rate, 3),
    }

@app.get("/documents")
def list_documents(user_id: str = Depends(require_auth)):
    """List all indexed documents for the current user."""
    docs = []
    for doc_id, doc in _engine.documents.items():
        if getattr(doc, "ownerId", None) != user_id:
            continue
        # Try to get storage URL
        try:
            url = _storage.get_url(doc_id)
        except Exception:
            url = doc.metadata.get("storage_url", f"storage://{doc_id}")

        # Get filename from metadata or derive from text
        filename = doc.metadata.get("filename", "")
        if not filename or filename == "Unknown file" or filename == "restored":
            # Derive from first line of cleaned text
            first_line = doc.cleanedText.strip().split('\n')[0].strip()[:50]
            if first_line:
                filename = first_line.replace('/', '-') + ".pdf"
            else:
                filename = f"document-{str(doc_id)[:8]}.pdf"
        page_count = doc.metadata.get("page_count", "?")
        chars = doc.metadata.get("chars", len(doc.cleanedText))

        docs.append({
            "document_id":  str(doc_id),
            "filename":     filename,
            "storage_url":  url,
            "keywords":     doc.keywords[:8],   # first 8 keywords as preview
            "page_count":   page_count,
            "chars":        chars,
            "index_timestamp": doc.indexTimestamp.isoformat(),
            "text_preview": doc.cleanedText[:120],
        })

    # Sort newest first
    docs.sort(key=lambda x: x["index_timestamp"], reverse=True)
    return {"count": len(docs), "documents": docs}

@app.get("/documents/{document_id}")
def get_document(document_id: str, user_id: str = Depends(require_auth)):
    """Retrieve full details of a single indexed document."""
    try:
        uid = UUID(document_id)
        if uid not in _engine.documents:
            raise HTTPException(status_code=404, detail="Document not found")
        doc = _engine.documents[uid]
        if getattr(doc, "ownerId", None) != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
            
        try:
            url = _storage.get_url(uid)
        except Exception:
            url = doc.metadata.get("storage_url", f"storage://{uid}")
        
        fname = doc.metadata.get("filename", "")
        if not fname or fname == "Unknown file" or fname == "restored":
            first_line = doc.cleanedText.strip().split('\n')[0].strip()[:50]
            fname = (first_line.replace('/', '-') + ".pdf") if first_line else f"document-{str(uid)[:8]}.pdf"

        return {
            "document_id":      str(uid),
            "filename":         fname,
            "storage_url":      url,
            "cleaned_text":     doc.cleanedText,
            "keywords":         doc.keywords,
            "page_count":       doc.metadata.get("page_count", 1),
            "pages":            doc.metadata.get("pages", [doc.cleanedText]),
            "chars":            doc.metadata.get("chars", len(doc.cleanedText)),
            "index_timestamp":  doc.indexTimestamp.isoformat(),
            "metadata":         doc.metadata,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug")
def debug():
    docs = list(_engine.documents.values())
    return {
        "indexed_count": len(docs),
        "documents": [{
            "document_id":          str(d.documentId),
            "keywords":             d.keywords,
            "page_count":           len(d.metadata.get("pages", [])) if hasattr(d, "metadata") else "?",
            "cleaned_text_preview": d.cleanedText[:300],
        } for d in docs],
    }
