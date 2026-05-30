import { useEffect, useState } from "react";
import { api } from "../api";
import { usePolling } from "../hooks";
import type { Prompt } from "../types";
import { fmtRelativeTime } from "../format";
import { Empty, ErrorBanner, Spinner } from "../components/common";

export function Prompts() {
  const { data, error, loading } = usePolling(api.prompts, 8000);
  const [selected, setSelected] = useState<string | null>(null);
  const [versions, setVersions] = useState<Prompt[]>([]);

  useEffect(() => {
    if (!selected) return;
    api.promptVersions(selected).then(setVersions).catch(() => setVersions([]));
  }, [selected]);

  async function rollback(name: string, version: number) {
    await api.rollbackPrompt(name, version);
    const v = await api.promptVersions(name);
    setVersions(v);
  }

  return (
    <div>
      <h1 className="page-title">Prompt registry</h1>
      {error && <ErrorBanner error={error} />}
      {loading && !data ? (
        <Spinner />
      ) : !data || data.length === 0 ? (
        <Empty>
          No prompts registered. POST to <code>/api/prompts</code> to version your
          first prompt.
        </Empty>
      ) : (
        <div className="split">
          <div className="panel" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Active version</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data.map((p) => (
                  <tr key={p.name} onClick={() => setSelected(p.name)}>
                    <td>{p.name}</td>
                    <td>v{p.version}</td>
                    <td style={{ color: "var(--muted)" }}>
                      {fmtRelativeTime(p.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selected && (
            <div className="panel">
              <h3>{selected} - version history</h3>
              {versions.map((v) => (
                <div
                  key={v.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    padding: "10px 0",
                  }}
                >
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <strong>v{v.version}</strong>
                    {v.is_active && (
                      <span className="badge ok">active</span>
                    )}
                    <span style={{ color: "var(--muted)", marginLeft: "auto" }}>
                      {fmtRelativeTime(v.created_at)}
                    </span>
                    {!v.is_active && (
                      <button onClick={() => rollback(selected, v.version)}>
                        Roll back to this
                      </button>
                    )}
                  </div>
                  {v.description && (
                    <p style={{ color: "var(--muted)", margin: "6px 0 0" }}>
                      {v.description}
                    </p>
                  )}
                  <pre className="payload" style={{ marginTop: 8 }}>
                    {v.template}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
