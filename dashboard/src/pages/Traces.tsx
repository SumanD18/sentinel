import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type TraceFilters } from "../api";
import { usePolling } from "../hooks";
import { fmtCost, fmtDuration, fmtRelativeTime, fmtTokens } from "../format";
import { Empty, ErrorBanner, Spinner, StatusBadge, TrustBadge } from "../components/common";

export function Traces() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<TraceFilters>({ limit: 100 });
  const { data, error, loading } = usePolling(
    () => api.traces(filters),
    5000,
    [JSON.stringify(filters)],
  );

  return (
    <div>
      <h1 className="page-title">Traces</h1>

      <div className="toolbar">
        <input
          type="text"
          placeholder="Filter by service…"
          onChange={(e) =>
            setFilters((f) => ({ ...f, service: e.target.value || undefined }))
          }
        />
        <select
          onChange={(e) =>
            setFilters((f) => ({ ...f, status: e.target.value || undefined }))
          }
        >
          <option value="">All statuses</option>
          <option value="ok">OK</option>
          <option value="error">Error</option>
        </select>
        <select
          onChange={(e) =>
            setFilters((f) => ({
              ...f,
              has_alert: e.target.value === "" ? undefined : e.target.value === "true",
            }))
          }
        >
          <option value="">All traces</option>
          <option value="true">Flagged only</option>
          <option value="false">Clean only</option>
        </select>
      </div>

      {error && <ErrorBanner error={error} />}
      {loading && !data ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <Empty>No traces yet. Point the SDK at this collector to get started.</Empty>
      ) : (
        <div className="panel" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Root</th>
                <th>Service</th>
                <th>Status</th>
                <th>Spans</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Duration</th>
                <th>Trust</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.trace_id} onClick={() => navigate(`/traces/${t.trace_id}`)}>
                  <td>
                    {t.has_alert && (
                      <span title="Has alert" style={{ color: "var(--danger)" }}>
                        ●{" "}
                      </span>
                    )}
                    {t.root_name ?? t.trace_id.slice(0, 8)}
                  </td>
                  <td style={{ color: "var(--muted)" }}>{t.service_name}</td>
                  <td>
                    <StatusBadge status={t.status} />
                  </td>
                  <td>
                    {t.span_count}
                    <span style={{ color: "var(--muted)" }}> ({t.llm_call_count} llm)</span>
                  </td>
                  <td>{fmtTokens(t.total_tokens)}</td>
                  <td>{fmtCost(t.total_cost_usd)}</td>
                  <td>{fmtDuration(t.duration_ms)}</td>
                  <td>
                    <TrustBadge score={t.min_trust_score} />
                  </td>
                  <td style={{ color: "var(--muted)" }}>{fmtRelativeTime(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
