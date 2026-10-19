// ==============================================================================
// 스마트 통신 쉼터 PWA Service Worker (sw.js)
// 안드로이드 OS 시스템 트레이 실제 알림(Native Android Notification) & 오프라인 캐시 제어
// ==============================================================================

const CACHE_NAME = 'smart-shelter-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/badge-72.png'
];

// 1. 서비스 워커 설치 (Install)
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker 설치 중...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] 정적 자산 캐싱 완료');
            return cache.addAll(ASSETS_TO_CACHE).catch(() => {});
        }).then(() => self.skipWaiting())
    );
});

// 2. 서비스 워커 활성화 (Activate)
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker 활성화 완료');
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

// 3. 안드로이드 시스템 푸시 이벤트 수신 (Server Push)
self.addEventListener('push', (event) => {
    let payload = {
        title: '⚠️ [스마트 통신 쉼터 알림]',
        body: '현재 위치의 Wi-Fi 통신 환경을 확인하세요.',
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/badge-72.png',
        vibrate: [200, 100, 200, 100, 200],
        tag: 'smart-shelter-alert',
        renotify: true,
        data: { url: '/' }
    };

    if (event.data) {
        try {
            const data = event.data.json();
            payload = Object.assign(payload, data);
        } catch (e) {
            payload.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(payload.title, {
            body: payload.body,
            icon: payload.icon || '/static/icons/icon-192.png',
            badge: payload.badge || '/static/icons/badge-72.png',
            vibrate: payload.vibrate || [200, 100, 200],
            tag: payload.tag || 'smart-shelter-alert',
            renotify: true,
            requireInteraction: true,
            data: payload.data || { url: '/' },
            actions: [
                { action: 'open_map', title: '📍 지도 확인' },
                { action: 'close', title: '닫기' }
            ]
        })
    );
});

// 4. 안드로이드 상단바 알림 클릭 이벤트 (Notification Click)
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] 안드로이드 시스템 알림 클릭 감지:', event.action);
    event.notification.close();

    if (event.action === 'close') {
        return;
    }

    const targetUrl = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            // 이미 열려 있는 탭이 있으면 포커스
            for (const client of clientList) {
                if ('focus' in client) {
                    client.postMessage({
                        type: 'NOTIFICATION_CLICKED',
                        action: event.action,
                        data: event.notification.data
                    });
                    return client.focus();
                }
            }
            // 열려 있는 창이 없으면 새 창으로 앱 실행
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});

// 5. 알림 닫기 이벤트
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] 알림이 사용자에 의해 닫혔습니다.');
});
