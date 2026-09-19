export function money(n) {
  return Number(n).toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function emptyBars() {
  return {
    amount_matches: { pass: 0, review: 0, fail: 0 },
    scope_covered: { pass: 0, review: 0, fail: 0 },
  };
}

export function emptyThroughput(total = 0) {
  return { done: 0, total, perSec: 0, elapsedMs: 0, usage: emptyUsage() };
}

export function emptyUsage() {
  return { inputTokens: 0, outputTokens: 0, pricePerMtok: 0, costUsd: null };
}

export function formatDuration(ms) {
  const s = Math.max(0, ms) / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${(s - m * 60).toFixed(0).padStart(2, "0")}s`;
}

export function formatCost(usd) {
  if (usd == null) return "—";
  if (usd === 0) return "$0.00";
  if (usd < 0.01) return `${(usd * 100).toFixed(3)}¢`;
  return `$${usd.toFixed(usd < 1 ? 4 : 2)}`;
}
