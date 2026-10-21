import io
import json
from types import SimpleNamespace

import groq
import httpx
import pytest

import app as app_module
from tests.test_resume import GOOD_RESUME


@pytest.fixture
def client(monkeypatch):
    app_module.app.config["TESTING"] = True
    app_module.limiter.enabled = False
    monkeypatch.setattr(
        app_module,
        "analyze_match",
        lambda resume, jd: {
            "is_job_description": True,
            "score": 72,
            "matched_skills": ["Python"],
            "missing_skills": ["Docker"],
            "summary": "Good fit.",
        },
    )
    monkeypatch.setattr(app_module, "generate_cover_letter", lambda *a, **k: "Dear Team,\n\nHello.")
    monkeypatch.setattr(app_module, "tailor_resume", lambda *a, **k: GOOD_RESUME)
    monkeypatch.setattr(app_module, "verify_cover_letter", lambda *a, **k: ["Mentions CI/CD: not in resume"])
    with app_module.app.test_client() as c:
        yield c


def test_health(client):
    assert client.get("/api/health").status_code == 200


def test_analyze_requires_resume(client):
    response = client.post("/api/analyze", data={"job_input": "Backend role", "resume_text": ""})
    assert response.status_code == 400


def test_analyze_returns_tailored_resume_and_warnings(client):
    response = client.post(
        "/api/analyze",
        data={
            "job_input": "Backend role needing Python and Docker.",
            "resume_text": "Jon Doe. Python developer with 4 years of experience.",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["score"] == 72
    assert body["cover_letter"].startswith("Dear Team")
    assert body["tailored_resume"]["name"] == "Jon Doe"
    assert "fact_warnings" in body
    assert body["cover_letter_warnings"] == ["Mentions CI/CD: not in resume"]


def test_non_job_page_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "analyze_match",
        lambda resume, jd: {"is_job_description": False, "summary": "This is a login page."},
    )
    response = client.post(
        "/api/analyze",
        data={"job_input": "Welcome back. Log in to continue.", "resume_text": "Jon Doe."},
    )
    assert response.status_code == 400


def test_failed_tailoring_returns_clean_error(client, monkeypatch):
    def broken(*a, **k):
        raise ValueError("tailored resume failed validation twice")

    monkeypatch.setattr(app_module, "tailor_resume", broken)
    response = client.post(
        "/api/analyze",
        data={"job_input": "Backend role needing Python.", "resume_text": "Jon Doe."},
    )
    assert response.status_code == 502
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"retry-after": "12"}, 12),
        ({"retry-after": "0.4"}, 1),
        ({"x-ratelimit-reset-tokens": "7.66s"}, 8),
        ({"x-ratelimit-reset-tokens": "1m26.4s"}, 87),
        ({"x-ratelimit-reset-tokens": "2h5m"}, 7500),
        ({"x-ratelimit-reset-tokens": "soon"}, None),
        ({}, None),
    ],
)
def test_groq_retry_after(headers, expected):
    assert app_module.groq_retry_after(headers) == expected


def test_groq_rate_limit_reports_wait(client, monkeypatch):
    def limited(*a, **k):
        req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        resp = httpx.Response(429, headers={"retry-after": "12"}, request=req)
        raise groq.RateLimitError("rate limited", response=resp, body=None)

    monkeypatch.setattr(app_module, "analyze_match", limited)
    response = client.post(
        "/api/analyze",
        data={"job_input": "Backend role needing Python.", "resume_text": "Jon Doe."},
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "12"
    assert response.get_json()["retry_after"] == 12
    assert "12 seconds" in response.get_json()["error"]


def test_resume_pdf_export_requires_data(client):
    response = client.post("/api/export/resume-pdf", json={})
    assert response.status_code == 400


def test_resume_pdf_export_returns_pdf(client):
    response = client.post("/api/export/resume-pdf", json={"resume": GOOD_RESUME})
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


def test_resume_docx_export_returns_word_file(client):
    response = client.post("/api/export/resume-docx", json={"resume": GOOD_RESUME})
    assert response.status_code == 200
    assert response.data.startswith(b"PK")
    assert "tailored_resume.docx" in response.headers["Content-Disposition"]


def test_cover_letter_export_still_routes_correctly(client):
    response = client.post("/api/export/pdf", json={"cover_letter": "Dear Team,\n\nHello."})
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


FRONTEND_DSN = "https://abc123@o1.ingest.us.sentry.io/456"


def envelope(dsn):
    header = json.dumps({"event_id": "0" * 32, "dsn": dsn})
    return f'{header}\n{{"type":"event"}}\n{{"message":"boom"}}\n'.encode()


def test_sentry_tunnel_forwards_to_our_project(client, monkeypatch):
    monkeypatch.setenv("SENTRY_FRONTEND_DSN", FRONTEND_DSN)
    sent = {}

    def fake_post(url, data, headers, timeout):
        sent.update(url=url, data=data)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(app_module.requests, "post", fake_post)
    body = envelope(FRONTEND_DSN)
    response = client.post("/api/monitoring", data=body, content_type="text/plain")
    assert response.status_code == 200
    assert sent == {"url": "https://o1.ingest.us.sentry.io/api/456/envelope/", "data": body}


@pytest.mark.parametrize(
    "dsn",
    [
        "https://abc123@o1.ingest.us.sentry.io/999",  # another project
        "https://abc123@evil.example.com/456",  # another host
        "http://abc123@o1.ingest.us.sentry.io/456",  # not https
    ],
)
def test_sentry_tunnel_rejects_other_destinations(client, monkeypatch, dsn):
    monkeypatch.setenv("SENTRY_FRONTEND_DSN", FRONTEND_DSN)
    monkeypatch.setattr(app_module.requests, "post", lambda *a, **k: pytest.fail("forwarded"))
    response = client.post("/api/monitoring", data=envelope(dsn), content_type="text/plain")
    assert response.status_code == 403


def test_sentry_tunnel_rejects_garbage(client, monkeypatch):
    monkeypatch.setenv("SENTRY_FRONTEND_DSN", FRONTEND_DSN)
    response = client.post("/api/monitoring", data=b"not json\n", content_type="text/plain")
    assert response.status_code == 400


def test_sentry_tunnel_off_without_config(client, monkeypatch):
    monkeypatch.delenv("SENTRY_FRONTEND_DSN", raising=False)
    response = client.post(
        "/api/monitoring", data=envelope(FRONTEND_DSN), content_type="text/plain"
    )
    assert response.status_code == 404
