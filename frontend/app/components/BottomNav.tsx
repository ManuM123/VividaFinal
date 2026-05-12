"use client";

import { usePathname } from "next/navigation";

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 mx-auto grid w-full max-w-[680px] grid-cols-2 gap-2 border-t border-[var(--line)] bg-[#fbf8ff]/90 px-4 py-3 backdrop-blur safe-bottom">
      <a
        className={`flex h-11 items-center justify-center rounded-lg font-black ${
          pathname.startsWith("/check-in")
            ? "bg-[var(--lavender)] text-white"
            : ""
        }`}
        href="/check-in"
      >
        Check-in
      </a>
      <a
        className={`flex h-11 items-center justify-center rounded-lg font-black ${
          pathname.startsWith("/progress")
            ? "bg-[var(--lavender)] text-white"
            : ""
        }`}
        href="/progress"
      >
        Progress
      </a>
    </nav>
  );
}
