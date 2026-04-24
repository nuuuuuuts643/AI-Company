const CACHE_NAME = 'flotopic-v7';

// HTML/JS/CSS: stale-while-revalidate (常にバックグラウンドで更新チェック)
const REVALIDATE_ASSETS = [
  '/',
  '/index.html',
  '/topic.html',
  '/mypage.html',
  '/catchup.html',
  '/storymap.html',
  '/legacy.html',
  '/style.css',
  '/app.js',
  '/config.js',
  '/manifest.json',
  '/js/auth.js',
  '/js/comments.js',
  '/js/favorites.js',
  '/js/utils.js',
];

// 画像・フォント: cache-first (変更頻度が低い)
const STATIC_EXTENSIONS = /\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|eot)$/;

// API paths: network-first
const API_PATHS = ['/api/'];

// Install: pre-cache
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(REVALIDATE_ASSETS))
  );
  self.skipWaiting();
});

// Activate: delete old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch handler
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Network-first for API calls
  if (API_PATHS.some(p => url.pathname.startsWith(p))) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Stale-while-revalidate for HTML/JS/CSS
  const isRevalidate = REVALIDATE_ASSETS.includes(url.pathname);
  if (isRevalidate) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(event.request).then(cached => {
          const fetchPromise = fetch(event.request).then(response => {
            if (response && response.status === 200) {
              cache.put(event.request, response.clone());
            }
            return response;
          }).catch(() => cached);
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  // Cache-first for images/fonts
  if (STATIC_EXTENSIONS.test(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response && response.status === 200) {
            const cloned = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
          }
          return response;
        });
      })
    );
    return;
  }

  // Network-first with cache fallback for everything else
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
        }
        return response;
      })
      .catch(() => {
        return caches.match(event.request).then(cached => {
          if (cached) return cached;
          if (event.request.mode === 'navigate') {
            return caches.match('/index.html');
          }
          return new Response('', { status: 503, statusText: 'Service Unavailable' });
        });
      })
  );
});

self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(data.title || 'Flotopic', {
    body: data.body || '新しいトピックが急上昇中です',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' }
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
