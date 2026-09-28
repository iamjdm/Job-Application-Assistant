"""Pulls text out of an uploaded resume/job-description file."""

import concurrent.futures
import io
import os
import zipfile

import docx
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Guards against a small compressed .docx that expands to something huge
# ("zip bomb") — checked against the zip's declared sizes, not by actually
# decompressing, so the check itself is cheap.
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

# A resume/job posting is never legitimately this long; a page count far
# beyond it is more likely an adversarially crafted PDF than real content.
MAX_PDF_PAGES = 50

# Backstop against a pathologically slow/hanging parse on a malformed file —
# bounds request latency even if the size/page checks above don't catch it.
EXTRACTION_TIMEOUT_SECONDS = 15

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class FileExtractionError(Exception):
    pass


def extract_text_from_file(file_storage) -> str:
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        if ext == ".doc":
            raise FileExtractionError(
                "Old .doc files aren't supported — re-save as .docx or PDF and try again."
            )
        raise FileExtractionError(
            f"Unsupported file type '{ext or 'unknown'}'. Upload a PDF, DOCX, or TXT file."
        )

    raw = file_storage.read()

    if ext == ".txt":
        run_extraction = lambda: raw.decode("utf-8", errors="ignore")
    elif ext == ".pdf":
        run_extraction = lambda: _extract_pdf(raw)
    else:  # .docx
        run_extraction = lambda: _extract_docx(raw)

    try:
        text = _executor.submit(run_extraction).result(timeout=EXTRACTION_TIMEOUT_SECONDS)
    except FileExtractionError:
        raise
    except concurrent.futures.TimeoutError:
        raise FileExtractionError(
            f"'{filename}' took too long to process and may be malformed — try a different file."
        )
    except Exception as e:
        raise FileExtractionError(
            f"Couldn't read '{filename}' — the file may be corrupted or not a valid "
            f"{ext[1:].upper()}."
        ) from e

    text = text.strip()
    if not text:
        raise FileExtractionError(
            f"Couldn't find any text in '{filename}' — it may be a scanned image without OCR text."
        )
    return text


def _extract_pdf(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise FileExtractionError(
            f"That PDF has too many pages (max {MAX_PDF_PAGES}) for a resume or job posting."
        )
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise FileExtractionError(
            "That file expands to an unreasonable size when opened — it may be corrupted."
        )
    document = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in document.paragraphs)
