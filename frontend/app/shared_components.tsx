"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  EngagementSummary,
  GSE_QUESTIONS,
  SCALE_OPTIONS,
} from "./static_data_and_types";

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

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 mx-auto grid w-full max-w-[680px] grid-cols-2 gap-2 border-t border-[var(--line)] bg-[#fbf8ff]/90 px-4 py-3 backdrop-blur safe-bottom">
      <Link
        className={`flex h-11 items-center justify-center rounded-lg font-black ${
          pathname.startsWith("/check-in")
            ? "bg-[var(--lavender)] text-white"
            : ""
        }`}
        href="/check-in"
      >
        Check-in
      </Link>
      <Link
        className={`flex h-11 items-center justify-center rounded-lg font-black ${
          pathname.startsWith("/progress")
            ? "bg-[var(--lavender)] text-white"
            : ""
        }`}
        href="/progress"
      >
        Progress
      </Link>
    </nav>
  );
}

export function ScaleForm({
  title,
  score: total,
  answers,
  setAnswers,
}: {
  title: string;
  score: number;
  answers: number[];
  setAnswers: (answers: number[]) => void;
}) {
  return (
    <div className="mt-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-black">{title}</h2>
          <p className="mt-1 text-sm leading-6">Score range 10-40.</p>
        </div>
        <strong className="min-w-14 rounded-lg bg-[var(--lavender-soft)] px-3 py-2 text-center text-xl text-[var(--lavender-dark)]">
          {total}
        </strong>
      </div>
      <div className="grid gap-3">
        {GSE_QUESTIONS.map((question, index) => (
          <label
            className="grid gap-3 rounded-lg border border-[var(--line)] p-3"
            key={question}
          >
            <span className="font-bold leading-5">
              {index + 1}. {question}
            </span>
            <select
              className="rounded-lg border border-[var(--line)] bg-[#fffcff] px-3 py-3 outline-none focus:border-[var(--lavender)] focus:ring-4 focus:ring-purple-200"
              value={answers[index]}
              onChange={(event) => {
                const next = [...answers];
                next[index] = Number(event.target.value);
                setAnswers(next);
              }}
            >
              {SCALE_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {value} - {label}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
    </div>
  );
}

export function LotusProgress({
  engagement,
}: {
  engagement: EngagementSummary;
}) {
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[var(--lavender-soft)] p-4">
      <p className="text-xs font-black uppercase text-[var(--lavender-dark)]">
        Lotus trail
      </p>
      <div className="mt-2 flex items-end justify-between gap-4">
        <div>
          <strong className="text-3xl">{engagement.currentStreak}</strong>
          <span className="ml-2 font-bold">day streak</span>
          <p className="mt-1 text-sm">
            {engagement.todayCheckIns} check-in
            {engagement.todayCheckIns === 1 ? "" : "s"} today
          </p>
        </div>
        <div className="text-right text-2xl text-[var(--lotus)]">
          {"✦".repeat(Math.min(5, engagement.currentStreak || 1))}
        </div>
      </div>
    </div>
  );
}

export function BreathStage({
  active,
  label,
}: {
  active: boolean;
  label: string;
}) {
  return (
    <div className="grid min-h-72 place-items-center rounded-lg bg-[linear-gradient(160deg,var(--lavender-soft),#f7fbf5)]">
      <div className="grid place-items-center">
        <div className="grid aspect-square w-[min(58vw,250px)] place-items-center rounded-full border border-purple-200">
          <div
            className={`aspect-square w-[42%] rounded-full bg-[var(--lavender)] shadow-2xl shadow-purple-900/20 ${
              active ? "animate-[breathe_5.5s_ease-in-out_infinite]" : ""
            }`}
          />
        </div>
        <p className="mt-4 font-black text-[var(--lavender-dark)]">{label}</p>
      </div>
      <style jsx>{`
        @keyframes breathe {
          0%,
          100% {
            transform: scale(0.78);
          }
          48% {
            transform: scale(1.48);
          }
        }
      `}</style>
    </div>
  );
}

export function LotusMark() {
  return (
    <div className="grid h-28 place-items-center rounded-lg bg-[linear-gradient(160deg,var(--lavender-soft),var(--sage-soft))]">
      <div className="relative h-16 w-16">
        <span className="absolute left-1/2 top-0 h-16 w-9 -translate-x-1/2 rounded-full bg-[var(--lotus)]" />
        <span className="absolute bottom-1 left-1 h-11 w-9 -rotate-45 rounded-full bg-[var(--lavender)]" />
        <span className="absolute bottom-1 right-1 h-11 w-9 rotate-45 rounded-full bg-[var(--sage)]" />
      </div>
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--line)] p-3">
      <span className="text-xs font-black uppercase">{label}</span>
      <strong className="mt-1 block break-words">{value}</strong>
    </div>
  );
}

export { Button };
