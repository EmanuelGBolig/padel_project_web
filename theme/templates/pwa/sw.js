{% load static %}// Service Worker de TodoPadel (PWA).
// Habilita "instalar la app" (installable) y deja LISTO el push para cuando se
// active Web Push (VAPID). No cachea agresivo para no servir páginas viejas.
'use strict';

self.addEventListener('install', function (event) {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(self.clients.claim());
});

// Handler de fetch (requisito de instalabilidad en Android/Chrome). Pass-through:
// dejamos que la red maneje todo normalmente, sin cachear.
self.addEventListener('fetch', function (event) {
  // no-op: el navegador resuelve la request como siempre
});

// --- Notificaciones push (listo para cuando se active VAPID) ---
self.addEventListener('push', function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; }
  catch (e) { data = { body: event.data ? event.data.text() : '' }; }

  var title = data.title || 'TodoPadel';
  var options = {
    body: data.body || '',
    icon: '{% static "img/favicon_192.png" %}',
    badge: '{% static "img/favicon_192.png" %}',
    data: { url: data.url || '/' },
    tag: data.tag || undefined,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      for (var i = 0; i < wins.length; i++) {
        if (wins[i].url.indexOf(url) !== -1 && 'focus' in wins[i]) return wins[i].focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
