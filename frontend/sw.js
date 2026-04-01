// Minimal service worker — enables PWA install prompt + background notifications
const CACHE_NAME = 'home-assistant-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));

self.addEventListener('fetch', e => {
  // Pass all requests through — no offline caching
  e.respondWith(fetch(e.request));
});

// Show a notification via the SW so it works even when the tab is backgrounded
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const { title, body } = event.data;
    event.waitUntil(
      self.registration.showNotification(title, { body, icon: '/static/icon.svg' })
    );
  }
});

// Clicking a notification focuses or opens the app
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow('/');
    })
  );
});
