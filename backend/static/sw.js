// ── Service Worker de Sol (FIX 2026-09-08) ────────────────────────────────
// Chrome Android PROHÍBE `new Notification()` fuera de un Service Worker:
// aunque el permiso esté concedido, la llamada lanza o se ignora silenciosamente.
// Este SW es el canal oficial: la página le manda {type:'sol-notify'} por
// postMessage y él llama a registration.showNotification(), que sí funciona.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'sol-notify') {
    self.registration.showNotification(d.title || '☀️ Sol', {
      body: d.body || '',
      icon: '/static/sol_avatar_full.png',
      badge: '/static/sol_avatar_full.png',
      tag: 'sol-notify'
    });
  }
});

// Click en la notificación → traer la app al frente (no abrir otra pestaña)
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
    for (const c of cs) { c.focus(); return; }
    return self.clients.openWindow('/sol.html');
  }));
});
