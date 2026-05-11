export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--line)] p-3">
      <span className="text-xs font-black uppercase">{label}</span>
      <strong className="mt-1 block break-words">{value}</strong>
    </div>
  );
}
