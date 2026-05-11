import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vivida",
    short_name: "Vivida",
    description: "A speech-aware stress manager for self-efficacy support.",
    start_url: "/",
    display: "standalone",
    background_color: "#fbf8ff",
    theme_color: "#7c5fa8",
    icons: [
      {
        src: "/icons/icon-192.svg",
        sizes: "192x192",
        type: "image/svg+xml",
        purpose: "maskable",
      },
      {
        src: "/icons/icon-512.svg",
        sizes: "512x512",
        type: "image/svg+xml",
        purpose: "maskable",
      },
    ],
  };
}
