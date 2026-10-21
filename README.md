# Job Application Assistant

Paste or upload your resume and a job posting, and get back a tailored resume
for that specific job, a match score with skills you have and skills you're
missing, and a cover letter. The language model only rewords and reorders
experience you already have. It never invents skills or achievements.

## Features

- **Match score** with color-coded matched skills (green) and missing skills
  (red), so you can see at a glance where you fit.
- **Tailored resume** in a single-column, ATS-friendly layout. It's editable
  and downloadable as a PDF.
- **Cover letter** you can preview, edit, and download as a PDF.
- **Resume input** by pasting text or uploading a PDF, DOCX, or TXT file.
- **Job posting input** by pasting text, pasting a URL (the page is fetched
  and the description extracted), or uploading a file.
- **Tone options** for the cover letter: professional, formal,
  conversational, or enthusiastic.
- **Responsive UI** that works on desktop, tablet, and phone.

## Tech stack

- **Frontend:** React (Vite)
- **Backend:** Flask, served with waitress in production
- **LLM:** Groq API
- **File parsing:** `pypdf`, `python-docx`
- **URL extraction:** `trafilatura`
- **PDF rendering:** `reportlab`

## Getting started

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate   # or `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env      # then add your GROQ_API_KEY
python app.py
```

Runs on `http://localhost:5000` by default. See `.env.example` for all
configuration options: CORS origin, debug mode, host and port, trusted-proxy
settings for deployment, and HTTPS handling.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env       # set VITE_API_URL if the backend isn't local
npm run dev
```

Runs on `http://localhost:5173` by default.

## Deployment

The backend deploys to [Render](https://render.com) and the frontend to
[Vercel](https://vercel.com).

1. **Backend:** in Render, create a new Blueprint from this repo. It reads
   `render.yaml`. Enter `GROQ_API_KEY` when prompted and leave
   `FRONTEND_ORIGIN` blank for now. Once it's live, note the service URL.
2. **Frontend:** in Vercel, import the repo, set the root directory to
   `frontend`, and add `VITE_API_URL` set to the Render URL (no trailing
   slash). Vite bakes this in at build time, so redeploy if it changes.
3. **CORS:** back in Render, set `FRONTEND_ORIGIN` to the Vercel URL and
   redeploy.

Render's free tier spins down when idle, so the first request after a quiet
period can take 30 to 60 seconds.

## Free-tier note

The Groq free tier has a per-minute token limit. If you run several analyses
in quick succession you may see a slow response or a rate-limit message. Wait
about a minute and try again.

## Security notes

The app includes per-IP rate limiting, an SSRF guard on the job-URL fetcher
(it blocks requests to private and internal addresses, including ones reached
through redirects), file-upload safeguards against decompression bombs and
malformed files, restricted CORS, security response headers, and a production
WSGI server with proxy-aware IP detection.

HTTPS is handled by the hosting platform. Error monitoring uses
[Sentry](https://sentry.io) and is off unless `SENTRY_DSN` (backend) and
`VITE_SENTRY_DSN` (frontend) are set. Error reports leave out request bodies,
local variables, and user details, so resume text isn't sent to Sentry.
