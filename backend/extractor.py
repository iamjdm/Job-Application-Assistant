"""Turns whatever the user gave us (a URL or pasted text) into job description text."""

import re
import trafilatura

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class ExtractionError(Exception):
    pass


def get_job_description(job_input: str) -> str:
    job_input = job_input.strip()
    if not job_input:
        raise ExtractionError("No job description or URL provided.")

    if not _URL_RE.match(job_input):
        return job_input

    downloaded = trafilatura.fetch_url(job_input)
    if not downloaded:
        raise ExtractionError(
            "Couldn't fetch that URL. The site may block automated requests "
            "(common on LinkedIn) — try pasting the job description text instead."
        )

    extracted = trafilatura.extract(downloaded)
    if not extracted or len(extracted.strip()) < 50:
        raise ExtractionError(
            "Couldn't find job description text on that page — try pasting it instead."
        )

    return extracted
