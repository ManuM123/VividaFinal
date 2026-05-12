const CACHE_NAME = "vivida-assets-v4";
const STATIC_ASSETS = [
  "/manifest.webmanifest",
  "/icon-192x192.png",
  "/icon-512x512.png",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/_next/")
  ) {
    return;
  }

  if (event.request.mode === "navigate") {
    return;
  }

  if (!STATIC_ASSETS.includes(url.pathname)) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response.ok) {
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

self.addEventListener("push", (event) => {
  let data = {
    title: "Vivida",
    message: "A gentle check-in is ready when you are.",
    url: "/check-in",
    interaction: false,
    tag: "vivida-reminder",
  };

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() };
    } catch {
      data.message = event.data.text();
    }
  }

  const options = {
    body: data.message,
    icon: "/icon-192x192.png",
    badge: "/icon-192x192.png",
    vibrate: [80, 40, 80],
    tag: data.tag,
    requireInteraction: Boolean(data.interaction),
    data: {
      url: data.url || "/check-in",
      dateOfArrival: Date.now(),
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
  };

  event.waitUntil(
    self.registration.showNotification(data.title || "Vivida", options).then(() => {
      if ("setAppBadge" in navigator) {
        return navigator.setAppBadge(1).catch(() => {});
      }
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if ("clearAppBadge" in navigator) {
    event.waitUntil(navigator.clearAppBadge().catch(() => {}));
  }
  if (event.action === "close") {
    return;
  }
  event.waitUntil(clients.openWindow(event.notification.data?.url || "/check-in"));
});
