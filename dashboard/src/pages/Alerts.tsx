import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { usePolling } from "../hooks";
import { fmtRelativeTime } from "../format";
import { Empty, ErrorBanner, Spinner } from "../components/common";

export function Alerts() {
  const [showResolved, setShowResolved] = useState(false);
  const { data, error, loading, refresh } = usePolling(
    () => api.alerts({ resolved: showResolved ? undefined : false, limit: 200 }),
    5000,
    [showResolved],
  );

  async function resolve(id: number) {
    await api.resolveAlert(id);
    refresh();
  }

  return (
    <div>
      <h1 className="page-title">Alerts</h1>
      <div className="toolbar">
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
          />
          Include resolved
        </label>
      </div>

      {error && <ErrorBanner error={error} />}
      {loading && !data ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <Empty>No alerts. Your pipelines are behaving.</Empty>
      ) : (
        <div className="panel" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Rule</th>
                <th>Message</th>
                <th>Trace</th>
                <th>When</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id} style={{ cursor: "default" }}>
                  <td className={`sev-${a.severity}`}>{a.severity}</td>
                  <td>{a.rule}</td>
                  <td style={{ maxWidth: 480 }}>{a.message}</td>
                  <td>
                    <Link to={`/traces/${a.trace_id}`}>
                      {a.trace_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{fmtRelativeTime(a.created_at)}</td>
                  <td>
                    {!a.resolved && (
                      <button onClick={() => resolve(a.id)}>Resolve</button>
                    )}
                    {a.resolved && <span style={{ color: "var(--muted)" }}>resolved</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
