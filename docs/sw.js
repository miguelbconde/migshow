// MigShow: funciona sem internet com a última edição vista.
// Páginas: busca na rede primeiro (a edição nova aparece logo); sem rede, usa a cópia guardada.
const CACHE = 'migshow-v1';
const BASE = ['./', './index.html', './edicoes.html', './manifest.webmanifest',
  './icones/icone-192.png', './icones/icone-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const proprio = url.origin === self.location.origin;
  const fonte = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (!proprio && !fonte) return;
  if (req.mode === 'navigate' || req.destination === 'document') {
    e.respondWith(fetch(req).then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); return r; })
      .catch(() => caches.match(req).then(r => r || caches.match('./index.html'))));
    return;
  }
  e.respondWith(caches.match(req).then(r => r || fetch(req).then(n => {
    if (n.ok || n.type === 'opaque') { const c = n.clone(); caches.open(CACHE).then(x => x.put(req, c)); }
    return n;
  })));
});
