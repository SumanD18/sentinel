// Small display formatters shared across components.

export function fmtDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`;
  if (ms < 1000) return `${ms.toFixed(1)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function fmtCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return "-";
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(5)}`;
  return `$${usd.toFixed(4)}`;
}

export function fmtTokens(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

export function fmtNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export function fmtRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return new Date(iso).toLocaleString();
}

export function trustColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "var(--muted)";
  if (score >= 0.7) return "var(--ok)";
  if (score >= 0.5) return "var(--warn)";
  return "var(--danger)";
}

export const KIND_COLORS: Record<string, string> = {
  llm: "#6ea8fe",
  tool: "#ffc857",
  retrieval: "#9d8cff",
  agent: "#5ad1a0",
  chain: "#79e0ee",
  embedding: "#f78fb3",
  guardrail: "#ff6b6b",
  function: "#9aa5b1",
  unknown: "#9aa5b1",
};

export function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? KIND_COLORS.unknown;
}
