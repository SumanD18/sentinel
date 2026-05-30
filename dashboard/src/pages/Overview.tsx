import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { usePolling } from "../hooks";
import { fmtCost, fmtDuration, fmtNumber, fmtTokens, trustColor } from "../format";
import { ErrorBanner, Spinner, StatCard, TrustBadge } from "../components/common";

const PROVIDER_COLORS = ["#6ea8fe", "#5ad1a0", "#ffc857", "#9d8cff", "#f78fb3"];

export function Overview() {
  const { data, error, loading } = usePolling(api.overview, 5000);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBanner error={error} />;
  if (!data) return null;

  const costData = Object.entries(data.cost_by_model)
    .map(([model, cost]) => ({ model, cost: Number(cost.toFixed(6)) }))
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 8);

  const providerData = Object.entries(data.calls_by_provider).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div>
      <h1 className="page-title">Overview</h1>

      <div className="cards">
        <StatCard label="Traces" value={fmtNumber(data.total_traces)} />
        <StatCard
          label="LLM calls"
          value={fmtNumber(data.total_llm_calls)}
          sub={`${fmtNumber(data.total_spans)} spans total`}
        />
        <StatCard
          label="Tokens"
          value={fmtTokens(data.total_tokens)}
          sub={`${fmtNumber(data.total_tokens)} total`}
        />
        <StatCard label="Spend" value={fmtCost(data.total_cost_usd)} />
        <StatCard
          label="Mean trust"
          value={<span style={{ color: trustColor(data.mean_trust_score) }}>
            {data.mean_trust_score.toFixed(2)}
          </span>}
        />
        <StatCard
          label="Open alerts"
          value={
            <span style={{ color: data.open_alerts ? "var(--danger)" : "var(--ok)" }}>
              {data.open_alerts}
            </span>
          }
        />
        <StatCard label="Latency p50" value={fmtDuration(data.p50_latency_ms)} />
        <StatCard label="Latency p95" value={fmtDuration(data.p95_latency_ms)} />
      </div>

      <div className="grid-2">
        <div className="panel">
          <h3>Cost by model</h3>
          {costData.length === 0 ? (
            <div className="empty">No cost data yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={costData} layout="vertical" margin={{ left: 24 }}>
                <XAxis type="number" stroke="#8b94a3" tickFormatter={(v) => `$${v}`} />
                <YAxis
                  type="category"
                  dataKey="model"
                  stroke="#8b94a3"
                  width={120}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  formatter={(v: number) => fmtCost(v)}
                  contentStyle={{ background: "#1b2230", border: "1px solid #28303f" }}
                />
                <Bar dataKey="cost" fill="#6ea8fe" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="panel">
          <h3>Calls by provider</h3>
          {providerData.length === 0 ? (
            <div className="empty">No provider data yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={providerData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={55}
                  outerRadius={95}
                  paddingAngle={2}
                  label={(e) => `${e.name} (${e.value})`}
                >
                  {providerData.map((_, i) => (
                    <Cell key={i} fill={PROVIDER_COLORS[i % PROVIDER_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#1b2230", border: "1px solid #28303f" }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="panel">
        <h3>System trust</h3>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Aggregate trust across all evaluated LLM outputs:{" "}
          <TrustBadge score={data.mean_trust_score} />. Scores blend the weakest and
          mean evaluator dimensions, so a single failing check is never hidden by
          averaging.
        </p>
      </div>
    </div>
  );
}
