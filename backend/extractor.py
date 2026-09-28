"""Turns whatever the user gave us (a URL or pasted text) into job description text."""

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
import trafilatura

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_MAX_REDIRECTS = 5
_FETCH_TIMEOUT = 10
_GENERIC_FETCH_ERROR = (
    "Couldn't fetch that URL. It may block automated requests (common on "
    "LinkedIn), or it may not be a reachable public address — try pasting "
    "the job description text instead."
)


class ExtractionError(Exception):
    pass


def _is_safe_ip(ip) -> bool:
    # Unwrap IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1) — a known
    # SSRF-guard bypass if checked only as a raw IPv6 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


def _is_safe_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    return all(_is_safe_ip(ipaddress.ip_address(info[4][0])) for info in infos)


def _safe_fetch(url: str) -> str:
    """Fetches a user-supplied URL while blocking requests to private/internal
    addresses — including ones only reached after a redirect."""
    for _ in range(_MAX_REDIRECTS):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ExtractionError(_GENERIC_FETCH_ERROR)
        if not _is_safe_host(parsed.hostname):
            raise ExtractionError(_GENERIC_FETCH_ERROR)

        try:
            resp = requests.get(
                url,
                timeout=_FETCH_TIMEOUT,
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobAppAssistant/1.0)"},
            )
        except requests.RequestException:
            raise ExtractionError(_GENERIC_FETCH_ERROR)

        if resp.is_redirect:
            location = resp.headers.get("Location")
            if not location:
                raise ExtractionError(_GENERIC_FETCH_ERROR)
            url = urljoin(url, location)
            continue

        if resp.status_code != 200:
            raise ExtractionError(_GENERIC_FETCH_ERROR)

        return resp.text

    raise ExtractionError(_GENERIC_FETCH_ERROR)


def get_job_description(job_input: str) -> str:
    job_input = job_input.strip()
    if not job_input:
        raise ExtractionError("No job description or URL provided.")

    if not _URL_RE.match(job_input):
        return job_input

    html = _safe_fetch(job_input)

    extracted = trafilatura.extract(html)
    if not extracted or len(extracted.strip()) < 50:
        raise ExtractionError(
            "Couldn't find job description text on that page — try pasting it instead."
        )

    return extracted
