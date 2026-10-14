import copy

import pytest

from export import build_docx, build_pdf
from resume_checks import find_unsupported_facts, validate_resume
from resume_export import build_resume_pdf

SOURCE = """Jon Doe - Software Engineer
4 years experience building Flask services with PostgreSQL.
Built a REST API with 10 endpoints. Works at Acme Corp in 2024."""

GOOD_RESUME = {
    "name": "Jon Doe",
    "contact": ["jon@example.com"],
    "sections": [
        {"type": "text", "heading": "Professional Summary", "text": "Software engineer with 4 years of experience."},
        {
            "type": "entries",
            "heading": "Experience",
            "entries": [
                {
                    "title": "Software Engineer",
                    "title_right": "2024",
                    "subtitle": "Acme Corp",
                    "subtitle_right": "",
                    "bullets": ["Built a REST API with 10 endpoints using Flask and PostgreSQL."],
                }
            ],
        },
        {"type": "skills", "heading": "Skills", "items": [{"label": "Backend", "value": "Flask, PostgreSQL"}]},
    ],
}


def test_well_formed_resume_passes_validation():
    validate_resume(GOOD_RESUME)


def test_resume_without_sections_fails_validation():
    broken = copy.deepcopy(GOOD_RESUME)
    broken["sections"] = []
    with pytest.raises(ValueError):
        validate_resume(broken)


def test_unknown_section_type_fails_validation():
    broken = copy.deepcopy(GOOD_RESUME)
    broken["sections"][0]["type"] = "table"
    with pytest.raises(ValueError):
        validate_resume(broken)


def test_faithful_resume_has_no_fact_warnings():
    assert find_unsupported_facts(SOURCE, GOOD_RESUME) == []


def test_invented_number_is_flagged():
    fabricated = copy.deepcopy(GOOD_RESUME)
    fabricated["sections"][1]["entries"][0]["bullets"].append("Led a team of 12 engineers.")
    warnings = find_unsupported_facts(SOURCE, fabricated)
    assert any('"12"' in w for w in warnings)


def test_invented_employer_is_flagged():
    fabricated = copy.deepcopy(GOOD_RESUME)
    fabricated["sections"][1]["entries"][0]["subtitle"] = "Globex Industries"
    warnings = find_unsupported_facts(SOURCE, fabricated)
    assert any("Globex Industries" in w for w in warnings)


def test_pdf_export_produces_a_pdf():
    data = build_resume_pdf(GOOD_RESUME)
    assert data.startswith(b"%PDF")


def test_cover_letter_pdf_export_produces_a_pdf():
    assert build_pdf("Dear Team,\n\nI would like to apply.\n\nSincerely,\nJon").startswith(b"%PDF")


def test_docx_export_produces_a_zip_container():
    assert build_docx("Dear Team,\n\nI would like to apply.").startswith(b"PK")


def test_verification_returns_flagged_claims(monkeypatch):
    import llm

    class FakeMessage:
        content = '{"unsupported_claims": ["CI/CD workflows: not on resume"]}'

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletion:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeCompletion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llm, "get_client", lambda: FakeClient())
    assert llm.verify_cover_letter("resume", "letter") == ["CI/CD workflows: not on resume"]
