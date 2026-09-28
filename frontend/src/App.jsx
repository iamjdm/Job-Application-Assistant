import { useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000";
const API_URL = `${API_BASE}/api/analyze`;
const EXPORT_URL = `${API_BASE}/api/export`;

function scoreTier(score) {
  if (score >= 75) return "tier-high";
  if (score >= 45) return "tier-mid";
  return "tier-low";
}

function SourceField({ label, textPlaceholder, textValue, onTextChange, file, onFileChange, rows }) {
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

      {mode === "paste" ? (
        <textarea
          placeholder={textPlaceholder}
          value={textValue}
          onChange={(e) => onTextChange(e.target.value)}
          rows={rows}
        />
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

function App() {
  const [jobText, setJobText] = useState("");
  const [jobFile, setJobFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [resumeFile, setResumeFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tone, setTone] = useState("professional");
  const [result, setResult] = useState(null);
  const [coverLetterText, setCoverLetterText] = useState("");
  const [downloadFormat, setDownloadFormat] = useState(null);
  const [downloadError, setDownloadError] = useState("");

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
    if (resumeFile) {
      formData.append("resume_file", resumeFile);
    } else {
      formData.append("resume_text", resumeText);
    }

    try {
      const res = await fetch(API_URL, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Something went wrong.");
      }
      setResult(data);
      setCoverLetterText(data.cover_letter);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload(fmt) {
    setDownloadError("");
    setDownloadFormat(fmt);
    try {
      const res = await fetch(`${EXPORT_URL}/${fmt}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cover_letter: coverLetterText }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Couldn't generate the file.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cover_letter.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloadFormat(null);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Job Application Assistant</h1>
        <p>Paste or upload a job posting and your resume.</p>
      </header>

      <div className="layout">
        <form className="input-panel" onSubmit={handleSubmit}>
          <SourceField
            label="Job posting"
            textPlaceholder="https://... or paste the job description text"
            textValue={jobText}
            onTextChange={setJobText}
            file={jobFile}
            onFileChange={setJobFile}
            rows={8}
          />

          <SourceField
            label="Your resume"
            textPlaceholder="Paste your resume text"
            textValue={resumeText}
            onTextChange={setResumeText}
            file={resumeFile}
            onFileChange={setResumeFile}
            rows={12}
          />

          <label className="tone-field">
            Cover letter tone
            <select value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="professional">Professional</option>
              <option value="formal">Formal</option>
              <option value="conversational">Conversational</option>
              <option value="enthusiastic">Enthusiastic</option>
            </select>
          </label>

          <button type="submit" disabled={loading}>
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          {error && <p className="error">{error}</p>}
        </form>

        <div className="results-panel">
          {!result && !loading && (
            <p className="placeholder">Results will show up here.</p>
          )}
          {loading && <p className="placeholder">Scoring your fit...</p>}

          {result && (
            <>
              <section className="score-section">
                <div className={`score-circle ${scoreTier(result.score)}`}>
                  {result.score}
                </div>
                <p>{result.summary}</p>
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

              <section>
                <div className="cover-letter-header">
                  <h3>Cover letter (editable)</h3>
                  <div className="download-buttons">
                    <button
                      type="button"
                      className="download-button"
                      disabled={downloadFormat !== null}
                      onClick={() => handleDownload("pdf")}
                    >
                      {downloadFormat === "pdf" ? "Preparing…" : "Download PDF"}
                    </button>
                    <button
                      type="button"
                      className="download-button"
                      disabled={downloadFormat !== null}
                      onClick={() => handleDownload("docx")}
                    >
                      {downloadFormat === "docx" ? "Preparing…" : "Download Word"}
                    </button>
                  </div>
                </div>
                {downloadError && <p className="error">{downloadError}</p>}
                <textarea
                  className="cover-letter"
                  value={coverLetterText}
                  onChange={(e) => setCoverLetterText(e.target.value)}
                  rows={14}
                />
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
