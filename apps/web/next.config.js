/** @type {import('next').NextConfig} */

// The browser needs the API URL inlined into the bundle, which normally means a
// NEXT_PUBLIC_* variable. Some Vercel plans warn about (or refuse) public-prefixed
// variables, so a private SCAMSENSE_API_URL is accepted as well: next.config.js
// runs at build time on the server and can inline any value it can read.
const apiUrl = process.env.SCAMSENSE_API_URL || process.env.NEXT_PUBLIC_API_URL;

const nextConfig = {
  turbopack: {
    root: __dirname,
  },
  ...(apiUrl ? { env: { NEXT_PUBLIC_API_URL: apiUrl } } : {}),
  async headers() {
    return [
      {
        // The worker must never be served stale, or a fix would never reach users.
        source: '/sw.js',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=0, must-revalidate' },
          { key: 'Service-Worker-Allowed', value: '/' },
        ],
      },
      {
        source: '/manifest.webmanifest',
        headers: [{ key: 'Content-Type', value: 'application/manifest+json' }],
      },
    ];
  },
};

module.exports = nextConfig;