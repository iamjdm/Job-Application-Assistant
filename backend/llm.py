"""Groq calls: match score + gap analysis + cover letter."""

import json
import os

from groq import Groq

from resume_checks import validate_resume

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

Never claim any of the following unless the resume text states it explicitly: CI/CD or DevOps work; open-source contributions; code reviews; authorship or co-authorship of any paper; team, leadership, or collaboration roles; specific tools, languages, or frameworks; production or professional experience beyond what the resume says; years of experience beyond what the resume says; interest in an industry, sector, or mission (such as healthcare or patient care); enthusiasm for the company's products or services. If the job posting asks for something the resume doesn't show, leave it out rather than claiming it.

Do NOT put the candidate's name or contact info (email, LinkedIn, GitHub, phone) at the \
top as a header block. Start directly with "Dear ...". End with a closing line, then \
"Sincerely," on its own line, then the candidate's name on the next line. Then — ONLY \
if that exact contact info literally appears in the resume text provided — leave one \
blank line after the name and list their email / LinkedIn / GitHub, one per line. Never \
invent, guess, or placeholder-fill contact details that aren't verbatim in the resume \
text; if none appear, end with just the name and nothing after it."""


TAILOR_SYSTEM_PROMPT = """You rewrite a candidate's resume to target a specific job. \
Respond with ONLY valid JSON, no markdown fences, matching this shape:

{
  "name": "<candidate's full name>",
  "contact": ["<email>", "<linkedin or other profile>", ...],
  "sections": [
    {"type": "text", "heading": "Professional Summary", "text": "<2-3 sentences>"},
    {"type": "entries", "heading": "Experience", "entries": [
      {"title": "<job title>", "title_right": "<dates>",
       "subtitle": "<employer>", "subtitle_right": "<location>",
       "bullets": ["<achievement>", ...]}
    ]},
    {"type": "entries", "heading": "Projects", "entries": [ ...same shape... ]},
    {"type": "entries", "heading": "Education", "entries": [
      {"title": "<school>", "title_right": "<location>",
       "subtitle": "<degree>", "subtitle_right": "<graduation date>",
       "text": "<optional, e.g. relevant coursework>"}
    ]},
    {"type": "skills", "heading": "Skills", "items": [
      {"label": "<category>", "value": "<comma-separated items>"}
    ]}
  ]
}

Rules:
- Use ONLY facts that appear in the resume: employers, titles, dates, degrees, tools, \
projects, and achievements. Never invent experience, skills, metrics, employers, or dates. \
If the job asks for something the resume doesn't show, leave it out.
- You may reword bullets to use the job description's terminology, but only where the \
experience truthfully applies.
- Do not add purposes, outcomes, benefits, or labels the resume doesn't state. For example, \
don't describe a project as "personal," "collaborative," or "for teams" unless the resume says so. \
For a project's subtitle, use the technologies or organization exactly as the resume lists them.
- Put the most relevant entries and bullets first. Drop bullets that don't help this job.
- Keep entries in reverse-chronological order within each section.
- Contact items must appear verbatim in the resume. Never invent contact details.
- Keep it ATS-friendly: plain text, no tables, no symbols or icons, no markdown.
- Aim for about one page of content."""


def tailor_resume(resume_text: str, job_description: str) -> dict:
    client = get_client()
    for _ in range(2):
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": TAILOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}",
                },
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        try:
            resume = json.loads(completion.choices[0].message.content)
            validate_resume(resume)
            return resume
        except ValueError:
            continue
    raise ValueError("tailored resume failed validation twice")


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


VERIFY_SYSTEM_PROMPT = """You check a cover letter against a candidate's resume. List every claim in the letter that the resume does not explicitly support: activities, tools, roles, authorship, length of experience, interest in an industry or mission, or enthusiasm for the company's work. Do not flag wording that only rephrases what the resume says. Respond with ONLY valid JSON, no markdown fences, matching this shape:

{"unsupported_claims": ["<short quote from the letter>: <why the resume doesn't support it>"]}

If every claim is supported, return {"unsupported_claims": []}."""


def verify_cover_letter(resume_text: str, cover_letter: str) -> list[str]:
    client = get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"RESUME:\n{resume_text}\n\nCOVER LETTER:\n{cover_letter}",
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        claims = json.loads(completion.choices[0].message.content).get("unsupported_claims", [])
    except (ValueError, AttributeError):
        return []
    return [claim for claim in claims if isinstance(claim, str) and claim.strip()]


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
