export default function VerdictChip({ verdict }) {
  return <span className={`chip ${verdict || ""}`}>{verdict || "—"}</span>;
}
