/* Latent Space service worker: network first, so the site is always fresh online, and the
   last good copy (page, styles, today's positions, fonts) is shown when there is no signal. */
const CACHE = "latent-space-v1";
const CORE = ["./", "index.html", "style.css", "app.js", "score.js", "bg.js", "kartik.svg", "icon.svg", "manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const font = /^fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (url.origin !== self.location.origin && !font) return;
  // jobs.json is fetched with a cache-busting ?v=; keep one copy under its plain path
  const key = url.pathname.endsWith("/jobs.json") ? url.origin + url.pathname : req;
  e.respondWith(
    fetch(req).then((res) => {
      if (res.ok || res.type === "opaque") {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(key, copy));
      }
      return res;
    }).catch(() => caches.match(key).then((hit) => hit || caches.match("index.html")))
  );
});
