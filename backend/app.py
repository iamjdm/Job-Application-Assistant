import json
import os

import groq
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from extractor import ExtractionError, get_job_description
from file_extractor import FileExtractionError, extract_text_from_file
from llm import analyze_match, generate_cover_letter

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB
CORS(app)


@app.post("/api/analyze")
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


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large — max 10 MB."}), 413


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
