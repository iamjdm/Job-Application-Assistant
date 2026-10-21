import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Builds the Chrome extension (side panel + background script) into
// dist-extension/, which is what you load in chrome://extensions.
// It reuses the website's React app from src/.
export default defineConfig({
  plugins: [react()],
  root: 'extension',
  // Read .env files from frontend/, same as the website build.
  envDir: '..',
  // Chrome loads extension pages from the extension root, not a web server.
  base: './',
  build: {
    outDir: '../dist-extension',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        sidepanel: 'extension/sidepanel.html',
        background: 'extension/background.js',
      },
      output: {
        // manifest.json refers to the background script by this exact name.
        entryFileNames: (chunk) =>
          chunk.name === 'background' ? 'background.js' : 'assets/[name]-[hash].js',
      },
    },
  },
})
