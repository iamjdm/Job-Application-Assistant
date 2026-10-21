import io

import pytest
from werkzeug.datastructures import FileStorage

import extractor
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


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        self.is_redirect = False
        self.headers = {}


@pytest.mark.parametrize("status", [403, 429, 999])
def test_blocked_sites_get_paste_advice(monkeypatch, status):
    monkeypatch.setattr(extractor, "_is_safe_host", lambda host: True)
    monkeypatch.setattr(extractor.requests, "get", lambda *a, **k: FakeResponse(status))
    with pytest.raises(ExtractionError, match="doesn't allow automatic reading"):
        get_job_description("https://www.linkedin.com/jobs/view/123")


def test_page_without_job_text_gets_paste_advice(monkeypatch):
    monkeypatch.setattr(extractor, "_is_safe_host", lambda host: True)
    monkeypatch.setattr(
        extractor.requests, "get", lambda *a, **k: FakeResponse(200, "<html><body></body></html>")
    )
    with pytest.raises(ExtractionError, match="paste it here"):
        get_job_description("https://example.wd1.myworkdayjobs.com/job/123")
