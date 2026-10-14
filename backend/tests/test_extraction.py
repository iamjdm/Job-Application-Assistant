import io

import pytest
from werkzeug.datastructures import FileStorage

from extractor import ExtractionError, get_job_description
from file_extractor import FileExtractionError, extract_text_from_file


def upload(data: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(data), filename=filename)


def test_txt_resume_is_read():
    text = extract_text_from_file(upload(b"Jon Doe - Python developer", "resume.txt"))
    assert "Python developer" in text


def test_old_doc_format_is_rejected_with_guidance():
    with pytest.raises(FileExtractionError, match="re-save as .docx"):
        extract_text_from_file(upload(b"bytes", "resume.doc"))


def test_unknown_extension_is_rejected():
    with pytest.raises(FileExtractionError, match="Unsupported file type"):
        extract_text_from_file(upload(b"bytes", "resume.png"))


def test_corrupt_pdf_fails_cleanly():
    with pytest.raises(FileExtractionError, match="may be corrupted"):
        extract_text_from_file(upload(b"%PDF-1.4 garbage", "resume.pdf"))


def test_corrupt_docx_fails_cleanly():
    with pytest.raises(FileExtractionError, match="may be corrupted"):
        extract_text_from_file(upload(b"not a zip file", "resume.docx"))


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_internal_addresses_are_blocked(url):
    with pytest.raises(ExtractionError):
        get_job_description(url)


def test_pasted_text_is_returned_unchanged():
    text = "Backend Engineer: Python, Flask, PostgreSQL required."
    assert get_job_description(text) == text


def test_empty_job_input_is_rejected():
    with pytest.raises(ExtractionError):
        get_job_description("   ")
