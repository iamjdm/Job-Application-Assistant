import { useState } from "react";
import "./App.css";

const API_URL = "http://localhost:5000/api/analyze";

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
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    const formData = new FormData();
    formData.append("tone", "professional");
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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
                <div className="score-circle">{result.score}</div>
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
                <h3>Cover letter</h3>
                <textarea
                  className="cover-letter"
                  value={result.cover_letter}
                  readOnly
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
