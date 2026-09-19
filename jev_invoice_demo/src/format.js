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
  return { done: 0, total, perSec: 0, elapsedMs: 0 };
}
