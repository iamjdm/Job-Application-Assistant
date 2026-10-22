import { useEffect, useRef, useState } from "react";
import "./App.css";
import { readCurrentJobPage } from "./jobPage";
import { IS_EXTENSION, loadSavedResume, removeSavedResume, saveResume } from "./savedResume";

// The extension isn't served from the website, so it links there in full.
const PRIVACY_URL = IS_EXTENSION ? `${import.meta.env.VITE_SITE_URL}/privacy.html` : "/privacy.html";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000";
const API_URL = `${API_BASE}/api/analyze`;
const EXPORT_URL = `${API_BASE}/api/export`;

function scoreTier(score) {
  if (score >= 75) return { className: "tier-high", label: "Strong fit" };
  if (score >= 45) return { className: "tier-mid", label: "Moderate fit" };
  return { className: "tier-low", label: "Low fit" };
}

function DownloadMenu({ disabled, busy, onPick }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function closeOnOutsideClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  return (
    <div className="download-menu" ref={ref}>
      <button
        type="button"
        className="download-button"
        disabled={disabled || busy}
        onClick={() => setOpen((on) => !on)}
      >
        {busy ? "Preparing…" : "Download ▾"}
      </button>
      {open && (
        <div className="download-menu-list">
          <button type="button" onClick={() => { setOpen(false); onPick("pdf"); }}>
            PDF
          </button>
          <button type="button" onClick={() => { setOpen(false); onPick("docx"); }}>
            Word
          </button>
        </div>
      )}
    </div>
  );
}

function cleanResume(resume) {
  const copy = structuredClone(resume);
  copy.contact = (copy.contact || []).map((s) => s.trim()).filter(Boolean);
  for (const section of copy.sections) {
    if (section.type === "entries") {
      for (const entry of section.entries) {
        entry.bullets = (entry.bullets || []).map((b) => b.trim()).filter(Boolean);
      }
    }
    if (section.type === "skills") {
      section.items = section.items.filter((item) => item.label || item.value);
    }
  }
  return copy;
}

function SourceField({ label, action, textPlaceholder, textHint, textValue, onTextChange, file, onFileChange, rows }) {
  const [mode, setMode] = useState("paste");

  return (
    <div className="source-field">
      <div className="source-field-header">
        <span>{label}</span>
        <div className="mode-toggle">
          <button
            type="button"
            className={mode === "paste" ? "active" : ""}
            onClick={() => setMode("paste")}
          >
            Paste
          </button>
          <button
            type="button"
            className={mode === "upload" ? "active" : ""}
            onClick={() => setMode("upload")}
          >
            Upload file
          </button>
        </div>
      </div>

      {action}

      {mode === "paste" ? (
        <>
          <textarea
            placeholder={textPlaceholder}
            value={textValue}
            onChange={(e) => onTextChange(e.target.value)}
            rows={rows}
          />
          {textHint && <p className="field-hint">{textHint}</p>}
        </>
      ) : (
        <div className="file-drop">
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => onFileChange(e.target.files[0] || null)}
          />
          {file && <span className="file-name">{file.name}</span>}
          <p className="file-hint">PDF, DOCX, or TXT — max 10 MB</p>
        </div>
      )}
    </div>
  );
}

function SavedResume({ resume, onReplace, onRemove }) {
  const description = resume.file
    ? resume.file.name
    : `Pasted text (${resume.text.trim().split(/\s+/).length} words)`;

  return (
    <div className="source-field">
      <div className="source-field-header">
        <span>Your resume</span>
      </div>
      <div className="saved-resume">
        <span className="file-name">{description}</span>
        <p className="field-hint">Saved in this browser only, not on our server.</p>
        <div className="saved-resume-actions">
          <button type="button" onClick={onReplace}>
            Replace
          </button>
          <button type="button" className="danger" onClick={onRemove}>
            Remove saved resume
          </button>
        </div>
      </div>
    </div>
  );
}

function ResumePreview({ resume }) {
  return (
    <article className="resume-preview">
      <h2 className="rp-name">{resume.name}</h2>
      <p className="rp-contact">{(resume.contact || []).join(" | ")}</p>
      {resume.sections.map((section, si) => (
        <div className="rp-section" key={si}>
          <h4>{section.heading}</h4>
          {section.type === "text" && <p>{section.text}</p>}
          {section.type === "skills" &&
            section.items.map((item, ii) => (
              <p key={ii}>
                <strong>{item.label}:</strong> {item.value}
              </p>
            ))}
          {section.type === "entries" &&
            section.entries.map((entry, ei) => (
              <div className="rp-entry" key={ei}>
                <div className="rp-line">
                  <strong>{entry.title}</strong>
                  <span>{entry.title_right}</span>
                </div>
                <div className="rp-line">
                  <em>{entry.subtitle}</em>
                  <em>{entry.subtitle_right}</em>
                </div>
                {entry.text && <p>{entry.text}</p>}
                <ul>
                  {(entry.bullets || [])
                    .filter((b) => b.trim())
                    .map((b, bi) => (
                      <li key={bi}>{b}</li>
                    ))}
                </ul>
              </div>
            ))}
        </div>
      ))}
    </article>
  );
}

function ResumeEditor({ resume, onChange }) {
  function update(mutate) {
    const copy = structuredClone(resume);
    mutate(copy);
    onChange(copy);
  }

  return (
    <div className="resume-editor">
      <input
        className="resume-name"
        value={resume.name || ""}
        onChange={(e) => update((r) => { r.name = e.target.value; })}
      />
      <textarea
        rows={2}
        placeholder="Contact lines, one per line"
        value={(resume.contact || []).join("\n")}
        onChange={(e) => update((r) => { r.contact = e.target.value.split("\n"); })}
      />

      {resume.sections.map((section, si) => (
        <div className="resume-section" key={si}>
          <h4>{section.heading}</h4>

          {section.type === "text" && (
            <textarea
              rows={4}
              value={section.text || ""}
              onChange={(e) => update((r) => { r.sections[si].text = e.target.value; })}
            />
          )}

          {section.type === "skills" &&
            section.items.map((item, ii) => (
              <div className="resume-row" key={ii}>
                <input
                  placeholder="Category"
                  value={item.label || ""}
                  onChange={(e) => update((r) => { r.sections[si].items[ii].label = e.target.value; })}
                />
                <input
                  placeholder="Items"
                  value={item.value || ""}
                  onChange={(e) => update((r) => { r.sections[si].items[ii].value = e.target.value; })}
                />
              </div>
            ))}

          {section.type === "entries" &&
            section.entries.map((entry, ei) => (
              <div className="resume-entry" key={ei}>
                <div className="resume-row">
                  <input
                    placeholder="Title"
                    value={entry.title || ""}
                    onChange={(e) => update((r) => { r.sections[si].entries[ei].title = e.target.value; })}
                  />
                  <input
                    placeholder="Date or location"
                    value={entry.title_right || ""}
                    onChange={(e) => update((r) => { r.sections[si].entries[ei].title_right = e.target.value; })}
                  />
                </div>
                <div className="resume-row">
                  <input
                    placeholder="Organization or subtitle"
                    value={entry.subtitle || ""}
                    onChange={(e) => update((r) => { r.sections[si].entries[ei].subtitle = e.target.value; })}
                  />
                  <input
                    placeholder="Location or date"
                    value={entry.subtitle_right || ""}
                    onChange={(e) => update((r) => { r.sections[si].entries[ei].subtitle_right = e.target.value; })}
                  />
                </div>
                {entry.text !== undefined && (
                  <textarea
                    rows={2}
                    value={entry.text}
                    onChange={(e) => update((r) => { r.sections[si].entries[ei].text = e.target.value; })}
                  />
                )}
                <textarea
                  rows={Math.max(2, (entry.bullets || []).length)}
                  placeholder="Bullets, one per line"
                  value={(entry.bullets || []).join("\n")}
                  onChange={(e) => update((r) => { r.sections[si].entries[ei].bullets = e.target.value.split("\n"); })}
                />
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}

function App() {
  const [jobText, setJobText] = useState("");
  const [jobFile, setJobFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [resumeFile, setResumeFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tone, setTone] = useState("professional");
  const [result, setResult] = useState(null);
  const [view, setView] = useState("resume");
  const [editing, setEditing] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [editingCover, setEditingCover] = useState(false);
  const [showCoverPreview, setShowCoverPreview] = useState(false);
  const [resumeData, setResumeData] = useState(null);
  const [coverLetterText, setCoverLetterText] = useState("");
  const [downloading, setDownloading] = useState(null);
  const [downloadError, setDownloadError] = useState("");
  // Seconds left before Groq's rate limit resets, after a 429.
  const [cooldown, setCooldown] = useState(0);
  // Extension only: the resume remembered from an earlier analysis.
  const [savedResume, setSavedResume] = useState(null);
  const [replacingResume, setReplacingResume] = useState(false);
  const usingSavedResume = savedResume !== null && !replacingResume;

  useEffect(() => {
    if (!IS_EXTENSION) return;
    loadSavedResume()
      .then(setSavedResume)
      .catch(() => {});
  }, []);

  // Extension only: fill the job posting from the tab the user is on.
  const [readingPage, setReadingPage] = useState(false);
  const [pageError, setPageError] = useState("");

  async function handleUseJobPage() {
    setPageError("");
    setReadingPage(true);
    try {
      setJobText(await readCurrentJobPage());
      setJobFile(null);
    } catch (err) {
      setPageError(err.message);
    } finally {
      setReadingPage(false);
    }
  }

  function handleRemoveSavedResume() {
    removeSavedResume()
      .then(() => {
        setSavedResume(null);
        setReplacingResume(false);
      })
      .catch(() => setError("Couldn't remove the saved resume. Try again."));
  }

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => {
      // The backend's "try again in N seconds" message is stale once it hits zero.
      if (cooldown === 1) setError("");
      setCooldown(cooldown - 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    const formData = new FormData();
    formData.append("tone", tone);
    if (jobFile) {
      formData.append("job_file", jobFile);
    } else {
      formData.append("job_input", jobText);
    }
    const resumeInput = usingSavedResume
      ? savedResume
      : { file: resumeFile, text: resumeFile ? "" : resumeText };
    if (resumeInput.file) {
      formData.append("resume_file", resumeInput.file);
    } else {
      formData.append("resume_text", resumeInput.text);
    }

    try {
      const res = await fetch(API_URL, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 429 && data.retry_after) {
          setCooldown(data.retry_after);
        }
        throw new Error(data.error || "Something went wrong.");
      }
      setResult(data);
      setResumeData(data.tailored_resume || null);
      setCoverLetterText(data.cover_letter);
      setView("resume");
      setEditing(false);
      setShowPreview(false);
      setEditingCover(false);
      setShowCoverPreview(false);
      // Remember a new resume only once it has worked for an analysis.
      if (IS_EXTENSION && !usingSavedResume) {
        saveResume(resumeInput)
          .then(() => {
            setSavedResume(resumeInput);
            setReplacingResume(false);
            setResumeFile(null);
            setResumeText("");
          })
          .catch(() => {});
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function downloadFile(url, body, filename, key) {
    setDownloadError("");
    setDownloading(key);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Couldn't generate the file.");
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloading(null);
    }
  }

  function handleResumeDownload(fmt) {
    downloadFile(
      `${EXPORT_URL}/resume-${fmt}`,
      { resume: cleanResume(resumeData) },
      `tailored_resume.${fmt}`,
      `resume-${fmt}`,
    );
  }

  function handleCoverDownload(fmt) {
    downloadFile(
      `${EXPORT_URL}/${fmt}`,
      { cover_letter: coverLetterText },
      `cover_letter.${fmt}`,
      fmt,
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        {/* Chrome's side panel already shows the name above the extension. */}
        {!IS_EXTENSION && <h1>Job Application Assistant</h1>}
        <p>Paste or upload a job posting and your resume.</p>
      </header>

      <div className="layout">
        <form className="input-panel" onSubmit={handleSubmit}>
          <SourceField
            label="Job posting"
            action={
              IS_EXTENSION && (
                <div className="job-page-action">
                  <button type="button" onClick={handleUseJobPage} disabled={readingPage}>
                    {readingPage ? "Reading page..." : "Use this job page"}
                  </button>
                  {pageError && <p className="error">{pageError}</p>}
                </div>
              )
            }
            textPlaceholder="Paste the job description text"
            textHint={
              IS_EXTENSION
                ? "Click Use this job page to fill this in from the posting you're viewing, or paste the description here."
                : "You can also paste a link, but sites like LinkedIn, Indeed, and Workday block automatic reading. Pasting the text always works."
            }
            textValue={jobText}
            onTextChange={setJobText}
            file={jobFile}
            onFileChange={setJobFile}
            rows={8}
          />

          {usingSavedResume ? (
            <SavedResume
              resume={savedResume}
              onReplace={() => setReplacingResume(true)}
              onRemove={handleRemoveSavedResume}
            />
          ) : (
            <>
              <SourceField
                label="Your resume"
                textPlaceholder="Paste your resume text"
                textHint={
                  IS_EXTENSION
                    ? "After your first analysis, your resume is saved in this browser so you only add it once."
                    : undefined
                }
                textValue={resumeText}
                onTextChange={setResumeText}
                file={resumeFile}
                onFileChange={setResumeFile}
                rows={12}
              />
              {replacingResume && (
                <button
                  type="button"
                  className="keep-saved-resume"
                  onClick={() => setReplacingResume(false)}
                >
                  Keep using saved resume
                </button>
              )}
            </>
          )}

          <label className="tone-field">
            Cover letter tone
            <select value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="professional">Professional</option>
              <option value="formal">Formal</option>
              <option value="conversational">Conversational</option>
              <option value="enthusiastic">Enthusiastic</option>
            </select>
          </label>

          <button type="submit" disabled={loading || cooldown > 0}>
            {loading
              ? "Analyzing..."
              : cooldown > 0
                ? `Try again in ${cooldown > 90 ? `${Math.ceil(cooldown / 60)} min` : `${cooldown}s`}`
                : "Analyze"}
          </button>

          {cooldown > 0 ? (
            <p className="error">
              Groq&apos;s usage limit was reached. Analyze will unlock when it resets.
            </p>
          ) : (
            error && <p className="error">{error}</p>
          )}
        </form>

        <div className="results-panel">
          {!result && !loading && (
            <p className="placeholder">Results will show up here.</p>
          )}
          {loading && <p className="placeholder">Scoring your fit...</p>}

          {result && (
            <>
              <section className={`score-section ${scoreTier(result.score).className}`}>
                <div className="score-circle" aria-label={`Match score ${result.score} out of 100`}>
                  {result.score}
                </div>
                <div className="score-details">
                  <h3>Resume match score</h3>
                  <p className="score-tier">{scoreTier(result.score).label}</p>
                  <p>{result.summary}</p>
                </div>
              </section>

              <section>
                <h3>Matched skills</h3>
                <ul className="tag-list matched">
                  {result.matched_skills.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </section>

              <section>
                <h3>Missing skills</h3>
                <ul className="tag-list missing">
                  {result.missing_skills.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </section>

              <div className="mode-toggle view-toggle">
                <button
                  type="button"
                  className={view === "resume" ? "active" : ""}
                  onClick={() => setView("resume")}
                >
                  Tailored resume
                </button>
                <button
                  type="button"
                  className={view === "cover" ? "active" : ""}
                  onClick={() => setView("cover")}
                >
                  Cover letter
                </button>
              </div>

              {downloadError && <p className="error">{downloadError}</p>}

              {view === "resume" ? (
                <section>
                  <div className="cover-letter-header">
                    <h3>Tailored resume</h3>
                    <div className="download-buttons">
                      <button
                        type="button"
                        className="download-button"
                        disabled={!resumeData}
                        onClick={() => setShowPreview((on) => !on)}
                      >
                        {showPreview ? "Hide preview" : "Show preview"}
                      </button>
                      <button
                        type="button"
                        className="download-button"
                        disabled={!resumeData}
                        onClick={() => setEditing((on) => !on)}
                      >
                        {editing ? "Done editing" : "Edit"}
                      </button>
                      <DownloadMenu
                        disabled={!resumeData || downloading !== null}
                        busy={downloading?.startsWith("resume-")}
                        onPick={handleResumeDownload}
                      />
                    </div>
                  </div>
                  {result.fact_warnings?.length > 0 && (
                    <div className="fact-warnings">
                      <strong>Check these before you download:</strong>
                      <ul>
                        {result.fact_warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {resumeData && editing && (
                    <ResumeEditor resume={resumeData} onChange={setResumeData} />
                  )}
                  {resumeData && !editing && showPreview && <ResumePreview resume={resumeData} />}
                  {!resumeData && (
                    <p className="placeholder">No tailored resume was returned.</p>
                  )}
                </section>
              ) : (
                <section>
                  <div className="cover-letter-header">
                    <h3>Cover letter</h3>
                    <div className="download-buttons">
                      <button
                        type="button"
                        className="download-button"
                        onClick={() => setShowCoverPreview((on) => !on)}
                      >
                        {showCoverPreview ? "Hide preview" : "Show preview"}
                      </button>
                      <button
                        type="button"
                        className="download-button"
                        onClick={() => setEditingCover((on) => !on)}
                      >
                        {editingCover ? "Done editing" : "Edit"}
                      </button>
                      <DownloadMenu
                        disabled={downloading !== null}
                        busy={downloading === "pdf" || downloading === "docx"}
                        onPick={handleCoverDownload}
                      />
                    </div>
                  </div>
                  {result.cover_letter_warnings?.length > 0 && (
                    <div className="fact-warnings">
                      <strong>Check these claims before you send it:</strong>
                      <ul>
                        {result.cover_letter_warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {editingCover && (
                    <textarea
                      className="cover-letter"
                      value={coverLetterText}
                      onChange={(e) => setCoverLetterText(e.target.value)}
                      rows={14}
                    />
                  )}
                  {!editingCover && showCoverPreview && (
                    <div className="cover-preview">{coverLetterText}</div>
                  )}
                </section>
              )}
            </>
          )}
        </div>
      </div>

      <footer className="app-footer">
        <a href={PRIVACY_URL} target="_blank" rel="noreferrer">
          Privacy policy
        </a>
      </footer>
    </div>
  );
}

export default App;
