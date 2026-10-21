import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor

import groq
import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from export import build_docx, build_pdf
from extractor import ExtractionError, get_job_description
from file_extractor import FileExtractionError, extract_text_from_file
from llm import analyze_match, generate_cover_letter, tailor_resume, verify_cover_letter
from resume_checks import find_unsupported_facts
from resume_export import build_resume_docx, build_resume_pdf
# from resume_export import resume_to_text  # re-enable with before/after scoring

load_dotenv()

# Error monitoring, off unless SENTRY_DSN is set. Resumes are personal data, so
# keep request bodies, local variables (which hold resume text), and user info
# out of error reports.
if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0,
    )

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# In production this must be set to the real frontend origin(s), comma-separated
# (e.g. "https://jobapp.example.com"). Defaults to the local Vite dev server.
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
    if origin.strip()
]
CORS(app, origins=FRONTEND_ORIGINS)

# Adds security response headers (X-Content-Type-Options, X-Frame-Options,
# a baseline CSP, etc). force_https defaults off since most hosting platforms
# terminate TLS at a load balancer and forward plain HTTP internally — forcing
# it here too would cause a redirect loop. Set FORCE_HTTPS=true once you know
# the deployment terminates TLS at the app itself, not in front of it.
Talisman(
    app,
    force_https=os.environ.get("FORCE_HTTPS", "false").lower() == "true",
    content_security_policy={"default-src": "'none'"},  # JSON/file API, no HTML served
)

limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")


@app.errorhandler(429)
def rate_limited(_e):
    return jsonify({"error": "Too many requests — please wait a moment and try again."}), 429


def groq_retry_after(headers) -> int | None:
    """Seconds until Groq's limit resets, from its 429 response headers.

    Prefers the standard Retry-After header, falling back to Groq's
    x-ratelimit-reset-tokens, which looks like "7.66s" or "1m26.4s".
    """
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(1, math.ceil(float(retry_after)))
        except ValueError:
            pass
    reset = headers.get("x-ratelimit-reset-tokens", "")
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", reset)
    if reset and match:
        hours, minutes, seconds = (float(g) if g else 0 for g in match.groups())
        return max(1, math.ceil(hours * 3600 + minutes * 60 + seconds))
    return None


# A job posting is a few thousand characters; anything past this is almost always
# scraped boilerplate (nav menus, related-postings lists, etc.), not signal.
# Resumes get a far looser cap because the tailored output must include all of them.
MAX_JOB_CHARS = 6000
MAX_RESUME_CHARS = 15000


@app.post("/api/analyze")
@limiter.limit("10 per minute; 50 per hour")
def analyze():
    tone = request.form.get("tone", "professional")

    try:
        resume_file = request.files.get("resume_file")
        if resume_file and resume_file.filename:
            resume_text = extract_text_from_file(resume_file)
        else:
            resume_text = request.form.get("resume_text", "")

        job_file = request.files.get("job_file")
        if job_file and job_file.filename:
            job_description = extract_text_from_file(job_file)
        else:
            job_description = get_job_description(request.form.get("job_input", ""))
    except (FileExtractionError, ExtractionError) as e:
        return jsonify({"error": str(e)}), 400

    if not resume_text.strip():
        return jsonify({"error": "Resume text is required."}), 400

    resume_text = resume_text[:MAX_RESUME_CHARS]
    job_description = job_description[:MAX_JOB_CHARS]

    try:
        match = analyze_match(resume_text, job_description)
        if not match.get("is_job_description", True):
            return jsonify(
                {
                    "error": (
                        "That doesn't look like a job description "
                        f"({match.get('summary', 'the page content looks wrong')}). "
                        "If you used a URL, try the direct job posting link, or paste "
                        "the description text instead."
                    )
                }
            ), 400
        with ThreadPoolExecutor(max_workers=2) as pool:
            cover_future = pool.submit(generate_cover_letter, resume_text, job_description, tone)
            tailor_future = pool.submit(tailor_resume, resume_text, job_description)
            cover_letter = cover_future.result()
            tailored_resume = tailor_future.result()
        cover_warnings = verify_cover_letter(resume_text, cover_letter)
        # Before/after scoring disabled to conserve Groq free-tier quota.
        # tailored_match = analyze_match(resume_to_text(tailored_resume), job_description)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except groq.AuthenticationError:
        app.logger.exception("Groq authentication failed")
        return jsonify({"error": "Invalid Groq API key. Check backend/.env."}), 500
    except groq.RateLimitError as e:
        wait = groq_retry_after(e.response.headers)
        if wait is None:
            message = "Groq rate limit hit — wait a moment and try again."
        elif wait <= 90:
            message = f"Groq rate limit hit — try again in {wait} seconds."
        else:
            message = f"Groq rate limit hit — try again in about {round(wait / 60)} minutes."
        resp = jsonify({"error": message, "retry_after": wait})
        if wait is not None:
            resp.headers["Retry-After"] = str(wait)
        return resp, 429
    except groq.APIStatusError as e:
        app.logger.exception("Groq API error")
        return jsonify({"error": f"Groq API error: {e.message}"}), 502
    except groq.APIConnectionError:
        app.logger.exception("Could not reach Groq")
        return jsonify({"error": "Couldn't reach Groq — check your connection and try again."}), 502
    except json.JSONDecodeError:
        app.logger.exception("Groq returned non-JSON for the match analysis")
        return jsonify({"error": "The model returned an unexpected response. Try again."}), 502
    except ValueError:
        app.logger.exception("Tailored resume failed validation")
        return jsonify({"error": "Couldn't build a tailored resume from this input. Try again."}), 502

    return jsonify(
        {
            "score": match.get("score"),
            "matched_skills": match.get("matched_skills", []),
            "missing_skills": match.get("missing_skills", []),
            "summary": match.get("summary", ""),
            "cover_letter": cover_letter,
            "tailored_resume": tailored_resume,
            "fact_warnings": find_unsupported_facts(resume_text, tailored_resume),
            "cover_letter_warnings": cover_warnings,
            # "tailored_match": {...}  # re-enable with before/after scoring
            "job_description": job_description,
        }
    )


@app.post("/api/export/<fmt>")
@limiter.limit("30 per minute")
def export_cover_letter(fmt):
    cover_letter = (request.get_json(silent=True) or {}).get("cover_letter", "").strip()
    if not cover_letter:
        return jsonify({"error": "No cover letter text provided."}), 400

    if fmt == "pdf":
        data = build_pdf(cover_letter)
        mimetype = "application/pdf"
        filename = "cover_letter.pdf"
    elif fmt == "docx":
        data = build_docx(cover_letter)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "cover_letter.docx"
    else:
        return jsonify({"error": "Format must be 'pdf' or 'docx'."}), 400

    return Response(
        data,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/resume-<fmt>")
@limiter.limit("30 per minute")
def export_resume(fmt):
    resume = (request.get_json(silent=True) or {}).get("resume")
    if not isinstance(resume, dict) or not resume.get("sections"):
        return jsonify({"error": "No resume data provided."}), 400

    if fmt == "pdf":
        data = build_resume_pdf(resume)
        mimetype = "application/pdf"
    elif fmt == "docx":
        data = build_resume_docx(resume)
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        return jsonify({"error": "Format must be 'pdf' or 'docx'."}), 400

    return Response(
        data,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="tailored_resume.{fmt}"'},
    )


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large — max 10 MB."}), 413


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))

    if debug:
        # Flask's dev server: auto-reload + interactive debugger, local use only.
        app.run(debug=debug, host=host, port=port)
    else:
        # Flask's dev server explicitly warns against production use — waitress
        # is a real production-grade WSGI server, and unlike gunicorn it also
        # runs on Windows, so this same command works for local "prod mode"
        # testing and for an actual deployment.
        #
        # waitress strips X-Forwarded-For (etc.) by default, unless the
        # directly-connecting peer's IP matches TRUSTED_PROXY_IP — so a normal
        # visitor spoofing that header gets ignored, and it only takes effect
        # once genuinely deployed behind the specific proxy you name here.
        # "*" trusts any connecting peer, for platforms (e.g. Render) whose
        # load-balancer IPs change but which block direct outside access.
        from waitress import serve

        serve_kwargs = {"host": host, "port": port}
        trusted_proxy_ip = os.environ.get("TRUSTED_PROXY_IP")
        if trusted_proxy_ip:
            serve_kwargs["trusted_proxy"] = trusted_proxy_ip
            serve_kwargs["trusted_proxy_count"] = int(
                os.environ.get("TRUSTED_PROXY_COUNT", "1")
            )
            serve_kwargs["trusted_proxy_headers"] = {"x-forwarded-for"}
        serve(app, **serve_kwargs)
