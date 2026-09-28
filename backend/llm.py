"""Groq calls: match score + gap analysis + cover letter."""

import json
import os

from groq import Groq

MODEL = "openai/gpt-oss-120b"

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set (see backend/.env.example).")
        _client = Groq(api_key=api_key)
    return _client


ANALYSIS_SYSTEM_PROMPT = """You are a career coach helping a candidate assess how well \
their resume fits a job description. The "job description" text was scraped from a web \
page and may not actually be a job posting — it could be a login wall, an error page, a \
job-search results list, or something else unrelated. Respond with ONLY valid JSON, no \
markdown fences, matching this exact shape:

{
  "is_job_description": <true if the text describes an actual job/role, false otherwise>,
  "score": <integer 0-100, or null if is_job_description is false>,
  "matched_skills": [<string>, ...],
  "missing_skills": [<string>, ...],
  "summary": "<if is_job_description is false, briefly explain what the text actually looks like instead (e.g. 'This looks like a login page, not a job posting.'); otherwise a one or two sentence explanation of the score>"
}
"""

COVER_LETTER_SYSTEM_PROMPT = """You write concise, specific cover letters. Use ONLY the \
candidate's actual resume details and the job description's language. No generic \
filler ("I am writing to express my interest..."). Keep it under 300 words. \
Respond with plain text only — no markdown, no subject line, no placeholders like \
[Company Name] left unfilled if the company name is inferable from the job description.

Never invent skills, tools, projects, or experience that aren't in the resume text — \
this is the most important rule. If the resume is a poor or unrelated fit for the role, \
do not paper over that by fabricating relevant-sounding work. Instead, write an honest \
letter that (a) states genuine transferable qualities actually evidenced in the resume \
(e.g. discipline, leadership, attention to detail — only if the resume actually shows \
them), and (b) does not claim direct experience with tools/skills the resume never \
mentions. It is fine, and better, for the letter to read as a weaker fit than to contain \
a single fabricated claim.

Do NOT put the candidate's name or contact info (email, LinkedIn, GitHub, phone) at the \
top as a header block. Start directly with "Dear ...". End with a closing line, then \
"Sincerely," on its own line, then the candidate's name on the next line. Then — ONLY \
if that exact contact info literally appears in the resume text provided — leave one \
blank line after the name and list their email / LinkedIn / GitHub, one per line. Never \
invent, guess, or placeholder-fill contact details that aren't verbatim in the resume \
text; if none appear, end with just the name and nothing after it."""


def analyze_match(resume_text: str, job_description: str) -> dict:
    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}",
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)


def generate_cover_letter(resume_text: str, job_description: str, tone: str = "professional") -> str:
    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": COVER_LETTER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Tone: {tone}\n\nRESUME:\n{resume_text}\n\n"
                    f"JOB DESCRIPTION:\n{job_description}"
                ),
            },
        ],
        temperature=0.6,
    )
    return completion.choices[0].message.content.strip()
