// The extension remembers the user's resume between uses. It's kept in this
// browser's IndexedDB, on the user's computer only, which can hold the
// uploaded file itself. Chrome deletes it if the extension is uninstalled.

const DB_NAME = "job-app-assistant";
const STORE = "resume";
const KEY = "saved";

// True inside the Chrome extension, false on the website.
export const IS_EXTENSION = Boolean(globalThis.chrome?.runtime?.id);

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore(mode, action) {
  const db = await openDb();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = action(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

// A saved resume is { file, text }: the uploaded File, or null and the pasted text.
export async function loadSavedResume() {
  return (await withStore("readonly", (store) => store.get(KEY))) ?? null;
}

export function saveResume(resume) {
  return withStore("readwrite", (store) => store.put(resume, KEY));
}

export function removeSavedResume() {
  return withStore("readwrite", (store) => store.delete(KEY));
}
