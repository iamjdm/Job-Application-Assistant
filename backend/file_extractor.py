"""Pulls text out of an uploaded resume/job-description file."""

import io
import os

import docx
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


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

    try:
        if ext == ".txt":
            text = raw.decode("utf-8", errors="ignore")
        elif ext == ".pdf":
            text = _extract_pdf(raw)
        else:  # .docx
            text = _extract_docx(raw)
    except FileExtractionError:
        raise
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
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(raw: bytes) -> str:
    document = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in document.paragraphs)
