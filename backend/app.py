import json
import os

import groq
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from export import build_docx, build_pdf
from extractor import ExtractionError, get_job_description
from file_extractor import FileExtractionError, extract_text_from_file
from llm import analyze_match, generate_cover_letter

load_dotenv()

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

# Keeps combined prompt size well under Groq's per-minute token limits — a real
# resume or job posting is a few thousand characters; anything past this is almost
# always scraped boilerplate (nav menus, related-postings lists, etc.), not signal.
MAX_INPUT_CHARS = 6000


def _truncate(text: str) -> str:
    return text[:MAX_INPUT_CHARS]


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

    resume_text = _truncate(resume_text)
    job_description = _truncate(job_description)

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
        cover_letter = generate_cover_letter(resume_text, job_description, tone)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except groq.AuthenticationError:
        app.logger.exception("Groq authentication failed")
        return jsonify({"error": "Invalid Groq API key. Check backend/.env."}), 500
    except groq.RateLimitError:
        return jsonify({"error": "Groq rate limit hit — wait a moment and try again."}), 429
    except groq.APIStatusError as e:
        app.logger.exception("Groq API error")
        return jsonify({"error": f"Groq API error: {e.message}"}), 502
    except groq.APIConnectionError:
        app.logger.exception("Could not reach Groq")
        return jsonify({"error": "Couldn't reach Groq — check your connection and try again."}), 502
    except json.JSONDecodeError:
        app.logger.exception("Groq returned non-JSON for the match analysis")
        return jsonify({"error": "The model returned an unexpected response. Try again."}), 502

    return jsonify(
        {
            "score": match.get("score"),
            "matched_skills": match.get("matched_skills", []),
            "missing_skills": match.get("missing_skills", []),
            "summary": match.get("summary", ""),
            "cover_letter": cover_letter,
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
