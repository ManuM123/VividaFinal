const CACHE_NAME = "vivida-next-v2";
const APP_SHELL = [
  "/",
  "/check-in",
  "/progress",
  "/manifest.webmanifest",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.hostname.includes("supabase")) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response.ok && url.origin === self.location.origin) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached || caches.match("/"));

      return cached || networkFetch;
    }),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "vivida-reminder") {
    return;
  }

  event.waitUntil(
    self.registration.showNotification(event.data.title || "Vivida", {
      body: event.data.body || "Take one steady minute for yourself.",
      icon: "/icons/icon-192.svg",
      badge: "/icons/icon-192.svg",
      vibrate: [60, 40, 60],
      data: {
        url: "/check-in",
      },
      actions: [
        {
          action: "open",
          title: "Check in",
        },
        {
          action: "close",
          title: "Close",
        },
      ],
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "close") {
    return;
  }
  event.waitUntil(clients.openWindow(event.notification.data?.url || "/check-in"));
});
