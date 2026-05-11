import type { Metadata, Viewport } from "next";
import "./globals.css";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Vivida",
  description: "A mobile-first speech-aware stress manager for self-efficacy support.",
  applicationName: "Vivida",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#7c5fa8",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("h-full antialiased", "font-sans")}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
