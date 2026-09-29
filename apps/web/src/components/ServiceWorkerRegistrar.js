'use client';

import { useEffect } from 'react';

/**
 * Registers the service worker that powers share-to-ScamSense and the offline
 * fallback. Only in production: during development the worker would shadow hot
 * reloads and serve stale pages.
 */
export default function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') return;
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;

    const register = () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
        // A failed registration only costs the share target and offline page.
      });
    };

    if (document.readyState === 'complete') {
      register();
      return undefined;
    }
    window.addEventListener('load', register);
    return () => window.removeEventListener('load', register);
  }, []);

  return null;
}