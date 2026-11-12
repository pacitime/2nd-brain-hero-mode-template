// Service worker minimo: serve solo a rendere il Cruscotto una PWA installabile,
// così la Badging API (navigator.setAppBadge) accende il pallino rosso sull'icona del Dock.
// Nessuna cache: le richieste passano dritte alla rete (dati sempre freschi da ClickUp).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => { /* passthrough: gestisce la rete */ });
