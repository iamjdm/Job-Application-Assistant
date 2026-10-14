"""Structural validation and fabrication checks for tailored resumes."""

import re

SECTION_TYPES = {"text", "entries", "skills"}


def validate_resume(resume) -> None:
    if not isinstance(resume, dict):
        raise ValueError("resume is not an object")
    if not isinstance(resume.get("name"), str):
        raise ValueError("resume name missing")
    if not isinstance(resume.get("contact", []), list):
        raise ValueError("resume contact is not a list")
    sections = resume.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("resume has no sections")

    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("heading"), str):
            raise ValueError("section missing heading")
        kind = section.get("type")
        if kind not in SECTION_TYPES:
            raise ValueError(f"unknown section type: {kind}")
        if kind == "text" and not isinstance(section.get("text"), str):
            raise ValueError("text section missing text")
        if kind == "skills":
            items = section.get("items")
            if not isinstance(items, list) or not all(
                isinstance(i, dict) and isinstance(i.get("label"), str) and isinstance(i.get("value"), str)
                for i in items
            ):
                raise ValueError("skills section malformed")
        if kind == "entries":
            entries = section.get("entries")
            if not isinstance(entries, list):
                raise ValueError("entries section malformed")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("title"), str):
                    raise ValueError("entry missing title")
                bullets = entry.get("bullets", [])
                if not isinstance(bullets, list) or not all(isinstance(b, str) for b in bullets):
                    raise ValueError("entry bullets malformed")


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def find_unsupported_facts(source_text: str, resume: dict) -> list[str]:
    """Flags concrete details in the tailored resume that don't appear in the source.

    Checks numbers (including years), entry subtitles and titles, and skill items.
    Wording changes are not checked; only facts are.
    """
    source_norm = _normalize(source_text)
    source_numbers = set(re.findall(r"\d+", source_text))
    warnings: list[str] = []

    def check_phrase(phrase: str, label: str) -> None:
        phrase = phrase.strip()
        if phrase and _normalize(phrase) not in source_norm:
            warnings.append(f'{label} "{phrase}" does not appear in your original resume')

    def check_numbers(text: str) -> None:
        for number in set(re.findall(r"\d+", text)):
            if number not in source_numbers:
                warnings.append(f'Number "{number}" does not appear in your original resume')

    for section in resume.get("sections", []):
        if section.get("type") == "text":
            check_numbers(section.get("text", ""))
        elif section.get("type") == "skills":
            for item in section.get("items", []):
                for skill in item.get("value", "").split(","):
                    check_phrase(skill, "Skill")
        else:
            for entry in section.get("entries", []):
                check_phrase(entry.get("title", ""), "Title")
                check_phrase(entry.get("subtitle", ""), "Subtitle")
                check_numbers(entry.get("title_right", ""))
                check_numbers(entry.get("subtitle_right", ""))
                for bullet in entry.get("bullets", []):
                    check_numbers(bullet)

    return list(dict.fromkeys(warnings))
