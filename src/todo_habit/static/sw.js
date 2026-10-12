const CACHE_NAME = 'todo-habit-v1';
const PRECACHE_ASSETS = [
  '/static/app.css',
  '/static/htmx.min.js',
  '/static/offline.html',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/icon-maskable-192x192.png',
  '/static/icons/icon-maskable-512x512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon.ico',
];

// インストール時にコアリソースを事前キャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// 有効化時に古いキャッシュを整理
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// リクエスト処理
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // GET 以外のリクエスト（POST, DELETE 等）はキャッシュせず直接ネットワークへ
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // 同一オリジンのみ処理
  if (url.origin !== self.location.origin) {
    return;
  }

  // 1. ページナビゲーション（HTML取得）: Network-First
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // 成功したらキャッシュにも保存（直近訪れたページのオフライン閲覧用）
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(async () => {
          // ネットワーク失敗時: キャッシュにあればそれを返し、なければオフライン画面を表示
          const cachedResponse = await caches.match(request);
          if (cachedResponse) {
            return cachedResponse;
          }
          const offlinePage = await caches.match('/static/offline.html');
          return offlinePage || new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
        })
    );
    return;
  }

  // 2. 静的アセット (/static/*): Cache-First + ネットワーク更新
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // バックグラウンドで最新を取得してキャッシュ更新
          fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(request, networkResponse);
              });
            }
          }).catch(() => {/* オフライン時は無視 */});
          return cachedResponse;
        }

        // キャッシュにない場合はネットワークから取得してキャッシュに保存
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseClone);
            });
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // 3. その他（写真等のアップロードファイルなど）: Network-First
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});
