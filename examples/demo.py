"""Demo: DocuSense System

Shows how to wire up the application and exercise the main workflows:
  1. Upload a document
  2. Check processing status
  3. Search indexed documents
  4. Delete a document

Run from the project root:
    python examples/demo.py
"""

import io
import sys
import os

# Make sure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.application import OCRApplication
from src.cache import DocumentCache
from src.error_handler import ErrorLogger
from src.monitoring import MetricsCollector, HealthChecker
from src.ocr_service import MockOCRService, RateLimitedOCRService
from src.retry import IndexingRetryQueue
from src.search_engine import InMemorySearchEngine
from src.status_manager import StatusManager
from src.storage import LocalFileSystemStorage
from src.text_cleaner import TextCleaner
from src.validation import FileTypeValidator


def build_app(storage_path: str = "./data/demo_storage") -> OCRApplication:
    """Build the application with all components wired together."""
    storage = LocalFileSystemStorage(base_path=storage_path, encryption_enabled=False)
    ocr_service = RateLimitedOCRService(MockOCRService(mock_text="Invoice\nDate: 2024-01-15\nAmount: $500"))
    text_cleaner = TextCleaner()
    search_engine = InMemorySearchEngine()

    app = OCRApplication(
        storage=storage,
        ocr_service=ocr_service,
        text_cleaner=text_cleaner,
        search_engine=search_engine,
        status_manager=StatusManager(),
        document_cache=DocumentCache(),
        error_logger=ErrorLogger(),
        retry_queue=IndexingRetryQueue(),
        file_validator=FileTypeValidator(),
    )
    # Start the storage monitor so upload events trigger processing
    app._monitor.start()
    return app


def main():
    print("=" * 60)
    print("  DocuSense System — Demo")
    print("=" * 60)

    app = build_app()

    # ----------------------------------------------------------------
    # 1. Upload a document
    # ----------------------------------------------------------------
    print("\n[1] Uploading document...")
    fake_pdf = b"%PDF-1.4 fake invoice content"
    result = app.upload(fake_pdf, filename="invoice.pdf", content_type="application/pdf")
    doc_id = result.document_id
    print(f"    document_id : {doc_id}")
    print(f"    storage_url : {result.storage_url}")
    print(f"    status      : {result.status}")

    # ----------------------------------------------------------------
    # 2. Check status (processing happens synchronously in the monitor)
    # ----------------------------------------------------------------
    print("\n[2] Checking document status...")
    status_result = app.get_status(doc_id)
    print(f"    status      : {status_result.status}")
    if status_result.error_details:
        print(f"    error       : {status_result.error_details}")

    # ----------------------------------------------------------------
    # 3. Search
    # ----------------------------------------------------------------
    print("\n[3] Searching for 'invoice'...")
    hits = app.search("invoice")
    if hits:
        for h in hits:
            print(f"    doc_id  : {h.document_id}")
            print(f"    score   : {h.score:.3f}")
            print(f"    snippet : {h.snippet[:60]}...")
            print(f"    url     : {h.storage_url}")
    else:
        print("    (no results — document may still be processing)")

    # ----------------------------------------------------------------
    # 4. Delete
    # ----------------------------------------------------------------
    print("\n[4] Deleting document...")
    del_result = app.delete(doc_id)
    print(f"    storage_deleted : {del_result.storage_deleted}")
    print(f"    index_deleted   : {del_result.index_deleted}")
    print(f"    success         : {del_result.success}")

    # ----------------------------------------------------------------
    # 5. Health check
    # ----------------------------------------------------------------
    print("\n[5] Health check...")
    hc = HealthChecker()
    hc.register("storage", lambda: True)
    hc.register("search_engine", lambda: True)
    hc.register("ocr_service", lambda: True)
    status = hc.check_all()
    for check in status.checks:
        icon = "✓" if check.healthy else "✗"
        print(f"    {icon} {check.name}: {check.message} ({check.latency_ms:.1f}ms)")
    print(f"    overall healthy: {status.healthy}")

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
