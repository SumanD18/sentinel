import type { ReactNode } from "react";
import { trustColor } from "../format";

export function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub !== undefined && <div className="sub">{sub}</div>}
    </div>
  );
}

export function TrustBadge({ score }: { score: number | null | undefined }) {
  const color = trustColor(score);
  const text = score === null || score === undefined ? "n/a" : score.toFixed(2);
  return (
    <span style={{ color, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
      ● {text}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status === "error" ? "error" : "ok"}`}>{status}</span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div className="spinner">{label}</div>;
}

export function ErrorBanner({ error }: { error: Error }) {
  return (
    <div className="error-banner">
      Could not reach the Sentinel collector: {error.message}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
