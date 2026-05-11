export function LotusGlyph({ className = "" }: { className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <span className="absolute left-1/2 top-0 h-full w-[56%] -translate-x-1/2 rounded-full bg-[var(--lotus)]" />
      <span className="absolute bottom-[6%] left-[6%] h-[69%] w-[56%] -rotate-45 rounded-full bg-[var(--lavender)]" />
      <span className="absolute bottom-[6%] right-[6%] h-[69%] w-[56%] rotate-45 rounded-full bg-[var(--sage)]" />
    </div>
  );
}
