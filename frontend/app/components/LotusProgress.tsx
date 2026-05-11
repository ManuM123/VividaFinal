import { EngagementSummary } from "../static_data_and_types";

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
