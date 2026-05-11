import { LotusGlyph } from "./LotusGlyph";

export function LotusMark() {
  return (
    <div className="grid h-28 place-items-center rounded-lg bg-[linear-gradient(160deg,var(--lavender-soft),var(--sage-soft))]">
      <LotusGlyph className="h-16 w-16" />
    </div>
  );
}
