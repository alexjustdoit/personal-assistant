// Minimal service worker — enables PWA install prompt
// No caching: all requests pass through to the network
const CACHE_NAME = 'home-assistant-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));

self.addEventListener('fetch', e => {
  // Pass all requests through — no offline caching
  e.respondWith(fetch(e.request));
});
