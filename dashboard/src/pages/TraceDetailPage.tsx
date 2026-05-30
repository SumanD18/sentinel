import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { usePolling } from "../hooks";
import type { Span } from "../types";
import { fmtCost, fmtDuration, fmtTokens } from "../format";
import { ErrorBanner, Spinner, StatusBadge, TrustBadge } from "../components/common";
import { Waterfall } from "../components/Waterfall";
import { SpanDetail } from "../components/SpanDetail";

export function TraceDetailPage() {
  const { id = "" } = useParams();
  const [selected, setSelected] = useState<Span | null>(null);
  // Poll once (traces are immutable once finished); keep light interval for
  // in-flight traces still receiving spans.
  const { data, error, loading } = usePolling(() => api.trace(id), 4000, [id]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBanner error={error} />;
  if (!data) return null;

  const active = selected ?? data.spans[0] ?? null;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link to="/traces">← All traces</Link>
      </div>
      <h1 className="page-title" style={{ marginBottom: 8 }}>
        {data.root_name ?? data.trace_id}
      </h1>
      <div className="toolbar" style={{ color: "var(--muted)", fontSize: 14 }}>
        <span>{data.service_name}</span>
        <StatusBadge status={data.status} />
        <span>{data.span_count} spans</span>
        <span>{fmtTokens(data.total_tokens)} tokens</span>
        <span>{fmtCost(data.total_cost_usd)}</span>
        <span>{fmtDuration(data.duration_ms)}</span>
        <span>
          trust <TrustBadge score={data.min_trust_score} />
        </span>
      </div>

      <div className="split">
        <div className="panel">
          <h3>Trace waterfall</h3>
          <Waterfall
            spans={data.spans}
            selectedId={active?.span_id ?? null}
            onSelect={setSelected}
          />
        </div>
        {active && <SpanDetail span={active} />}
      </div>
    </div>
  );
}
