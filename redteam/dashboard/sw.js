// Service Worker — PWA offline
const CACHE = "redteam-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./assets/styles.css",
  "./assets/app.js",
  "./assets/favicon.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Network-first para /api/*, cache-first para assets
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request).catch(() => new Response(JSON.stringify({ error: "offline" }), {
      headers: { "Content-Type": "application/json" }
    })));
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
