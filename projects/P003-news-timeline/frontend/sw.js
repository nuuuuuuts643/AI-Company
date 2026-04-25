const CACHE_NAME = 'flotopic-v9';

// config.js は絶対にキャッシュしない（APIのURLが変わると全機能が壊れるため）
const NEVER_CACHE = ['/config.js'];

// HTML/JS/CSS: network-first + cache fallback（SW更新時に古いJSが残らないように）
const NETWORK_FIRST_ASSETS = [
  '/',
  '/index.html',
  '/topic.html',
  '/mypage.html',
  '/catchup.html',
  '/storymap.html',
  '/legacy.html',
  '/style.css',
  '/app.js',
  '/manifest.json',
  '/js/auth.js',
  '/js/comments.js',
  '/js/favorites.js',
  '/js/notifications.js',
  '/js/theme.js',
  '/js/utils.js',
];

// 画像・フォント: cache-first（変更頻度が低い）
const STATIC_EXTENSIONS = /\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|eot)$/;

// API paths: network-first
const API_PATHS = ['/api/'];

// Install: pre-cache + 即座に有効化
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(NETWORK_FIRST_ASSETS))
  );
  self.skipWaiting();
});

// Activate: 旧キャッシュを全削除して即座に制御を奪う
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch handler
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // config.js は常にネットワークから取得（キャッシュしない）
  if (NEVER_CACHE.includes(url.pathname)) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Network-first for API
  if (API_PATHS.some(p => url.pathname.startsWith(p))) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const r = response.clone(); caches.open(CACHE_NAME).then(c => c.put(event.request, r));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Network-first for HTML/JS/CSS（オフライン時はキャッシュにフォールバック）
  if (NETWORK_FIRST_ASSETS.includes(url.pathname)) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const r = response.clone(); caches.open(CACHE_NAME).then(c => c.put(event.request, r));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
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
            const r = response.clone(); caches.open(CACHE_NAME).then(c => c.put(event.request, r));
          }
          return response;
        });
      })
    );
    return;
  }

  // Network-first fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const r = response.clone(); caches.open(CACHE_NAME).then(c => c.put(event.request, r));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then(cached => {
          if (cached) return cached;
          if (event.request.mode === 'navigate') return caches.match('/index.html');
          return new Response('', { status: 503, statusText: 'Service Unavailable' });
        })
      )
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
