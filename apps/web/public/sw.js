/**
 * ScamSense service worker.
 *
 * Two jobs, both entirely on-device:
 *   1. Share target: the manifest posts shared text/URL/images to /share, which
 *      this worker intercepts. The payload is parked in IndexedDB (files are
 *      Blobs, so they cannot travel in a URL) and the user is sent to /check.
 *   2. Offline fallback: navigations are network-first; if the network is gone
 *      the cached offline page answers instead of a browser error page.
 *
 * It never caches API traffic and never caches anything cross-origin.
 */
const CACHE_NAME = 'scamsense-shell-v1';
const OFFLINE_URL = '/offline';
const PRECACHE = [OFFLINE_URL, '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png'];
const SHARE_PATH = '/share';
const DB_NAME = 'scamsense-share';
const DB_STORE = 'payload';
const DB_KEY = 'latest';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(DB_STORE)) db.createObjectStore(DB_STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function writePayload(payload) {
  const db = await openDatabase();
  await new Promise((resolve, reject) => {
    const transaction = db.transaction(DB_STORE, 'readwrite');
    transaction.objectStore(DB_STORE).put(payload, DB_KEY);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

async function handleShare(request) {
  const redirectTo = (target) =>
    new Response(null, { status: 303, headers: { Location: target } });

  try {
    const form = await request.formData();
    const field = (name) => {
      const value = form.get(name);
      return typeof value === 'string' ? value : '';
    };
    const file = form.get('image');
    const image = file && typeof file !== 'string' && file.size ? file : null;
    const payload = {
      title: field('title').slice(0, 300),
      text: field('text').slice(0, 5000),
      url: field('url').slice(0, 2000),
      image: image,
      at: Date.now(),
    };
    const hasContent = payload.text.trim() || payload.url.trim() || payload.image;
    if (!hasContent) return redirectTo('/check?shared=empty');

    await writePayload(payload);
    return redirectTo('/check?shared=1');
  } catch (error) {
    return redirectTo('/check?shared=error');
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;

  if (request.method === 'POST' && url.pathname === SHARE_PATH) {
    event.respondWith(handleShare(request));
    return;
  }

  if (request.method !== 'GET') return;
  // Never cache analysis traffic; the assistant and results must stay live.
  if (url.pathname.startsWith('/api/') || url.pathname === '/analyses') return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        const cached = (await cache.match(OFFLINE_URL)) || (await cache.match('/check'));
        return cached || new Response('ScamSense is offline.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' },
        });
      })
    );
  }
});