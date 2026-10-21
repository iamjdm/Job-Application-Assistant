# Job Application Assistant

Paste or upload your resume and a job posting, and get back a tailored resume
for that specific job, a match score with skills you have and skills you're
missing, and a cover letter. The language model only rewords and reorders
experience you already have. It never invents skills or achievements.

It runs as a website and as a Chrome extension that reads the job posting
straight from the page you're on.

## Features

- **Match score** with color-coded matched skills (green) and missing skills
  (red), so you can see at a glance where you fit.
- **Tailored resume** in a single-column, ATS-friendly layout. It's editable
  and downloadable as a PDF.
- **Cover letter** you can preview, edit, and download as a PDF.
- **Resume input** by pasting text or uploading a PDF, DOCX, or TXT file.
- **Job posting input** by pasting text or uploading a file. You can also
  paste a link, but many job sites (LinkedIn, Indeed, Workday) block
  automatic reading, so the app explains when to paste the text instead.
- **Tone options** for the cover letter: professional, formal,
  conversational, or enthusiastic.
- **Responsive UI** that works on desktop, tablet, and phone.

### Chrome extension

- **Side panel** that opens beside the job posting when you click the
  toolbar icon, with the same results, editing, and downloads as the website.
- **Use this job page** reads the job description from the current tab, with
  no copying or highlighting. It uses the page's schema.org `JobPosting` data
  where available, built-in support for LinkedIn, Indeed, Greenhouse, Lever,
  Workday, Ashby, and UltiPro, and a reader-mode fallback for other sites.
  Highlighted text takes priority if you want to pick the text yourself.
- **Saved resume:** after your first analysis, your resume is remembered in
  the browser (on your computer only) until you replace or remove it.

## Tech stack

- **Frontend:** React (Vite)
- **Backend:** Flask, served with waitress in production
- **LLM:** Groq API
- **File parsing:** `pypdf`, `python-docx`
- **URL extraction:** `trafilatura`
- **PDF rendering:** `reportlab`
- **Extension:** Chrome Manifest V3 side panel, built from the same React app
- **Error monitoring:** Sentry

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

### Chrome extension

```bash
cd frontend
npm run build:extension
```

This builds the extension into `frontend/dist-extension/`, using the settings
in `frontend/.env.extension` (the live backend URL, the website URL, and the
Sentry DSN). Then load it in Chrome:

1. Go to `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and select `frontend/dist-extension`.
3. Pin the extension and click its icon to open the side panel.

After rebuilding, click the reload button on the extension's card and reopen
the side panel. The key in `frontend/extension/public/manifest.json` gives the
extension a fixed ID, `kpaoihciabmiphhknggkeeblmdhjjofa`, on every computer,
so the backend's CORS setting can allow it.

The extension's source is in `frontend/extension/` (manifest, background
script, side panel page, and icons). Extension-only behavior in `src/` (the
saved resume and page reading) switches on only when running inside the
extension, so the website is unaffected.

### Tests

From the repo root:

```bash
(cd backend && pytest)            # backend tests
(cd frontend && npm run lint)     # frontend lint
```

GitHub Actions runs both, plus the frontend build, on every push.

## Deployment

The backend deploys to [Render](https://render.com) and the frontend to
[Vercel](https://vercel.com).

1. **Backend:** in Render, create a new Blueprint from this repo. It reads
   `render.yaml`. Enter `GROQ_API_KEY` when prompted and leave
   `FRONTEND_ORIGIN` blank for now. Once it's live, note the service URL.
2. **Frontend:** in Vercel, import the repo, set the root directory to
   `frontend`, and add `VITE_API_URL` set to the Render URL (no trailing
   slash). Vite bakes this in at build time, so redeploy if it changes.
3. **CORS:** back in Render, set `FRONTEND_ORIGIN` to the Vercel URL and the
   extension's address, separated by a comma with no trailing slashes:
   `https://<your-app>.vercel.app,chrome-extension://kpaoihciabmiphhknggkeeblmdhjjofa`.
   Then redeploy.
4. **Error monitoring (optional):** create a Flask project and a React project
   in Sentry. In Render, set `SENTRY_DSN` to the Flask project's DSN and
   `SENTRY_FRONTEND_DSN` to the React project's DSN. In Vercel, set
   `VITE_SENTRY_DSN` to the React project's DSN and redeploy.

Render's free tier spins down when idle, so the first request after a quiet
period can take 30 to 60 seconds.

## Free-tier note

The Groq free tier allows about 8,000 tokens per minute, and each analysis
makes four model calls. If you run several analyses in quick succession, the
Analyze button counts down until the limit resets. The limit is shared by
everyone using a deployment, so upgrade to a paid Groq plan before sharing it
widely.

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
Frontend reports are sent through the backend's `/api/monitoring` route so ad
blockers don't drop them. Set `SENTRY_FRONTEND_DSN` on the backend to the same
value as `VITE_SENTRY_DSN` to enable it. Extension reports are tagged with the
environment `extension`.

## Privacy

The privacy policy is at `frontend/public/privacy.html` and is served at
`/privacy.html` on the website. The app and the extension link to it. Resumes
and job postings are sent to the backend and Groq to produce results and are
not stored on the server. The extension's saved resume stays in the user's
browser. Update the policy if the app's handling of data changes.
