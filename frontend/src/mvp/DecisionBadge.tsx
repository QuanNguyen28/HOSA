export function DecisionBadge({ value }: { value: string | null | undefined }) {
  return (
    <span
      className={`inline-block border px-2 py-1 font-mono text-[10px] tracking-wider ${value === "PASS" ? "border-mint/40 text-mint" : value === "FAIL" ? "border-rose/40 text-rose" : "border-amber/40 text-amber"}`}
    >
      {value ?? "INDETERMINATE"}
    </span>
  );
}
