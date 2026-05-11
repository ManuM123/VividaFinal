"use client";

import { GSE_QUESTIONS, SCALE_OPTIONS } from "../static_data_and_types";

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
