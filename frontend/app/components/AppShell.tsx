"use client";

import { BottomNav } from "./BottomNav";

export function AppShell({
  title,
  status,
  children,
  showNav = false,
}: {
  title: string;
  status?: string;
  children: React.ReactNode;
  showNav?: boolean;
}) {
  return (
    <main className="app-bottom-space mx-auto flex min-h-dvh w-full max-w-[680px] flex-col px-4 pt-5">
      <header className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase text-[var(--lavender)]">
            Vivida
          </p>
          <h1 className="mt-1 text-4xl font-black leading-none tracking-normal text-[var(--foreground)]">
            {title}
          </h1>
        </div>
        {status && (
          <span className="rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-xs font-black shadow-sm">
            {status}
          </span>
        )}
      </header>
      {children}
      {showNav && <BottomNav />}
    </main>
  );
}
