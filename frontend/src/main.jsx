import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import './index.css'
import App from './App.jsx'

// Error monitoring, off unless VITE_SENTRY_DSN is set at build time. Session
// replay and performance tracing stay off, since the page shows resume text.
// Reports go through our backend (tunnel) because ad blockers block sentry.io.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN
const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5000'
// In the extension, file paths start with chrome-extension://<id>/, which
// Sentry's "browser extension errors" inbound filter drops as third-party
// noise. Relabel them as our own app's files so they get through.
const extensionRoot = globalThis.chrome?.runtime?.id ? globalThis.chrome.runtime.getURL('') : null
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    tunnel: `${apiBase}/api/monitoring`,
    environment: import.meta.env.MODE,
    sendDefaultPii: false,
    integrations: extensionRoot
      ? [Sentry.rewriteFramesIntegration({ root: extensionRoot, prefix: 'app:///' })]
      : [],
  })
}

createRoot(document.getElementById('root'), {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
  onRecoverableError: Sentry.reactErrorHandler(),
}).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
