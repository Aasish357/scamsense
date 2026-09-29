/**
 * Client-side reader for the payload the service worker parked in IndexedDB
 * when the user shared text, a link or an image into ScamSense.
 *
 * The worker stores a Blob for image shares, so nothing large ever travels in
 * a URL, and the payload is dropped as soon as it has been picked up.
 */
const DB_NAME = 'scamsense-share';
const DB_STORE = 'payload';
const DB_KEY = 'latest';
const MAX_AGE_MS = 5 * 60 * 1000;

function openDatabase() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(DB_STORE)) db.createObjectStore(DB_STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readSharedPayload() {
  try {
    const db = await openDatabase();
    const payload = await new Promise((resolve, reject) => {
      const request = db.transaction(DB_STORE, 'readonly').objectStore(DB_STORE).get(DB_KEY);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
    db.close();
    if (!payload || !payload.at || Date.now() - payload.at > MAX_AGE_MS) return null;
    return payload;
  } catch (error) {
    return null;
  }
}

export async function clearSharedPayload() {
  try {
    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(DB_STORE, 'readwrite');
      transaction.objectStore(DB_STORE).delete(DB_KEY);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
    db.close();
  } catch (error) {
    // Nothing to clear.
  }
}

export function composeSharedText(payload) {
  if (!payload) return '';
  return [payload.title, payload.text, payload.url]
    .map((part) => (part || '').trim())
    .filter(Boolean)
    .join('\n');
}