"""FastAPI web server for OCR Document Extraction System

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

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

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

_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_POPPLER   = (
    r"C:\Users\wbadi\AppData\Local\Microsoft\WinGet\Packages"
    r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\poppler-25.07.0\Library\bin"
)

# ---------------------------------------------------------------------------
# Real OCR service with per-page tracking
# ---------------------------------------------------------------------------

class RealFileOCRService(OCRServiceInterface):
    """Extracts real text from PDFs and images using Tesseract + pdfplumber."""

    # ── helpers ──────────────────────────────────────────────────────

    def _clean(self, text: str) -> str:
        """Strip non-ASCII garbage, collapse spaces, drop short lines."""
        chars = [c if (ord(c) < 128 and (c.isprintable() or c in " \n\t\r")) else " "
                 for c in text]
        cleaned = re.sub(r"[ \t]+", " ", "".join(chars))
        lines = [l.strip() for l in cleaned.splitlines() if len(l.strip()) >= 3]
        return "\n".join(lines).strip()

    def _tesseract_image(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT
            return pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes))).strip()
        except Exception:
            return ""

    def _pdf_pages(self, data: bytes):
        """Return list of per-page text strings (Tesseract preferred)."""
        # Primary: image-based OCR — handles custom/embedded fonts
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT
            images = convert_from_bytes(data, dpi=200, poppler_path=_POPPLER)
            return [pytesseract.image_to_string(img).strip() for img in images]
        except Exception:
            pass

        # Fallback: pdfplumber (text-based PDFs only)
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
    """After a document is indexed, attach its file hash to metadata."""
    doc_id_str = str(event.document_id)
    if doc_id_str in _pending_hashes:
        doc = _engine.documents.get(event.document_id)
        if doc:
            doc.metadata.update(_pending_hashes.pop(doc_id_str))
            _engine._save()

_status_mgr.register_change_callback(_attach_hash_on_index)

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="OCR Document Extraction", version="0.1.0")

_HTML_FILE = Path(__file__).parent / "static" / "index.html"

@app.get("/", response_class=HTMLResponse)
def index():
    return _HTML_FILE.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    import hashlib
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # Duplicate detection — hash the file content
    file_hash = hashlib.sha256(data).hexdigest()
    for doc_id, doc in _engine.documents.items():
        if doc.metadata.get("file_hash") == file_hash:
            # Already indexed — return existing document instead of re-processing
            return {
                "document_id": str(doc_id),
                "storage_url": doc.metadata.get("storage_url", f"storage://{doc_id}"),
                "status":      "INDEXED",
                "duplicate":   True,
                "message":     "This file was already uploaded and indexed.",
            }

    try:
        result = _app.upload(data, filename=file.filename, content_type=content_type)
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
def get_status(document_id: str):
    try:
        uid    = UUID(document_id)
        result = _app.get_status(uid)
        return {
            "document_id":  str(result.document_id),
            "status":       result.status,
            "error_details": result.error_details,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---------------------------------------------------------------------------
# Search — with page numbers
# ---------------------------------------------------------------------------

@app.get("/search")
def search(query: str, limit: int = 10, user_id: Optional[str] = None):
    try:
        hits = _app.search(query, limit=limit, user_id=user_id)
        results = []
        q_lower = query.lower()

        for h in hits:
            pages_found = []
            context_snippet = h.snippet  # fallback

            doc = _engine.documents.get(h.document_id)
            if doc:
                raw_pages = doc.metadata.get("pages", [])

                # Find pages containing the query
                for i, page_text in enumerate(raw_pages, start=1):
                    if q_lower in page_text.lower():
                        pages_found.append(i)

                # Build a context snippet: text around the first match
                full_text = doc.cleanedText
                idx = full_text.lower().find(q_lower)
                if idx != -1:
                    start = max(0, idx - 80)
                    end   = min(len(full_text), idx + 160)
                    context_snippet = ("..." if start > 0 else "") + \
                                      full_text[start:end].strip() + \
                                      ("..." if end < len(full_text) else "")

            results.append({
                "document_id": str(h.document_id),
                "score":       h.score,
                "snippet":     context_snippet,
                "storage_url": h.storage_url,
                "pages_found": pages_found,
            })

        return {"query": query, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@app.delete("/delete/{document_id}")
def delete(document_id: str):
    try:
        uid    = UUID(document_id)
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
def list_documents():
    """List all indexed documents."""
    docs = []
    for doc_id, doc in _engine.documents.items():
        # Try to get storage URL
        try:
            url = _storage.get_url(doc_id)
        except Exception:
            url = doc.metadata.get("storage_url", f"storage://{doc_id}")

        # Get filename from metadata or fallback
        filename = doc.metadata.get("filename", "Unknown file")
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
