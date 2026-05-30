import type { EvalResult, Span } from "../types";
import { fmtCost, fmtDuration, fmtTokens, trustColor } from "../format";
import { TrustBadge } from "./common";

function payload(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function EvalBar({ result }: { result: EvalResult }) {
  const color = trustColor(result.score);
  return (
    <div className="eval-row" title={result.explanation}>
      <span style={{ width: 130 }}>{result.evaluator}</span>
      <div className="meter">
        <span style={{ width: `${result.score * 100}%`, background: color }} />
      </div>
      <span style={{ color, width: 42, textAlign: "right" }}>
        {result.score.toFixed(2)}
      </span>
    </div>
  );
}

export function SpanDetail({ span }: { span: Span }) {
  return (
    <div className="panel">
      <h3>
        {span.name}{" "}
        <span className="badge kind" style={{ background: "var(--panel-2)", color: "var(--muted)" }}>
          {span.kind}
        </span>
      </h3>

      <div className="kv" style={{ marginBottom: 16 }}>
        <div className="k">Status</div>
        <div className={span.status === "error" ? "sev-critical" : ""}>
          {span.status}
          {span.status_message ? ` - ${span.status_message}` : ""}
        </div>
        <div className="k">Duration</div>
        <div>{fmtDuration(span.duration_ms)}</div>
        {span.model && (
          <>
            <div className="k">Model</div>
            <div>
              {span.provider ? `${span.provider} / ` : ""}
              {span.model}
            </div>
          </>
        )}
        {span.total_tokens > 0 && (
          <>
            <div className="k">Tokens</div>
            <div>
              {fmtTokens(span.total_tokens)}{" "}
              <span style={{ color: "var(--muted)" }}>
                ({span.prompt_tokens} in / {span.completion_tokens} out)
              </span>
            </div>
          </>
        )}
        {span.cost_usd !== null && (
          <>
            <div className="k">Cost</div>
            <div>{fmtCost(span.cost_usd)}</div>
          </>
        )}
        {span.trust_score !== null && (
          <>
            <div className="k">Trust score</div>
            <div>
              <TrustBadge score={span.trust_score} />
            </div>
          </>
        )}
      </div>

      {span.eval_results && span.eval_results.length > 0 && (
        <>
          <h3>Trust evaluation</h3>
          <div style={{ marginBottom: 16 }}>
            {span.eval_results.map((r) => (
              <EvalBar key={r.evaluator} result={r} />
            ))}
          </div>
        </>
      )}

      {span.input !== null && span.input !== undefined && (
        <>
          <h3>Input</h3>
          <pre className="payload">{payload(span.input)}</pre>
        </>
      )}
      {span.output !== null && span.output !== undefined && (
        <>
          <h3>Output</h3>
          <pre className="payload">{payload(span.output)}</pre>
        </>
      )}

      {Object.keys(span.attributes ?? {}).length > 0 && (
        <>
          <h3>Attributes</h3>
          <pre className="payload">{payload(span.attributes)}</pre>
        </>
      )}
    </div>
  );
}
