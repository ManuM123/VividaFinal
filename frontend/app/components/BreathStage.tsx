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
