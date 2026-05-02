const CACHE_NAME = 'flotopic-dev'; // デプロイ時にgit SHAで上書きされる（手動バージョン管理禁止）

// config.js は絶対にキャッシュしない（APIのURLが変わると全機能が壊れるため）
const NEVER_CACHE = ['/config.js'];

// HTML: network-only（T2026-0502-BI-CACHE-FIX で network-first から強化）
//   背景: スマホで UX 復旧反映遅れの構造対処。SW が古い HTML を cache fallback で
//         返すと「PR 出して deploy しても旧 SPA UX が残る」隙間が生じる。
//         HTML はサーバー側 no-store + SW network-only で必ず最新を取りに行く。
//         副作用: オフライン時に navigate 不可 (許容)。
const HTML_NETWORK_ONLY = [
  '/',
  '/index.html',
  '/topic.html',
  '/mypage.html',
  '/profile.html',
  '/catchup.html',
  '/storymap.html',
  '/about.html',
  '/terms.html',
  '/privacy.html',
  '/contact.html',
  '/manifest.json',
];

// JS/CSS: network-first + cache fallback（オフライン時の SPA 動作維持・?v=SHA で URL 変わるので古い cache は別エントリー）
const NETWORK_FIRST_ASSETS = [
  '/style.css',
  '/app.js',
  '/detail.js',
  '/js/auth.js',
  '/js/comments.js',
  '/js/favorites.js',
  '/js/history.js',
  '/js/notifications.js',
  '/js/theme.js',
  '/js/utils.js',
];

// 画像・フォント: cache-first（変更頻度が低い）
const STATIC_EXTENSIONS = /\.(png|jpg|jpeg|gif|webp|svg|ico|woff2?|ttf|eot)$/;

// API paths: network-first
const API_PATHS = ['/api/'];

// Install: 事前キャッシュなし（ページロードと競合しないよう遅延キャッシュに変更）
self.addEventListener('install', event => {
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

  // 外部ドメインはSWを素通り（CORSエラー防止・広告スクリプト正常動作のため）
  if (url.origin !== self.location.origin) return;

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

  // Network-only for HTML（T2026-0502-BI-CACHE-FIX）
  // SW で HTML を一切キャッシュしない。サーバー側 Cache-Control: no-store とペアで動作。
  // 副作用: オフライン時に navigate 不可 (許容・SPA 起動には JS / CSS / API も必要なので元々厳しい)。
  if (HTML_NETWORK_ONLY.includes(url.pathname) || event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request));
    return;
  }

  // Network-first for JS/CSS（?v=SHA で URL 変わるので古い cache は別エントリーになり害なし）
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
