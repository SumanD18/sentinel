import type { Span } from "../types";
import { fmtDuration, kindColor } from "../format";

interface Props {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}

interface Node {
  span: Span;
  depth: number;
}

/** Flatten the span tree into render order (parents before children), tracking
 *  depth for indentation. Orphan spans (missing parent) are treated as roots so
 *  nothing is ever hidden. */
function buildOrder(spans: Span[]): Node[] {
  const byParent = new Map<string | null, Span[]>();
  const ids = new Set(spans.map((s) => s.span_id));
  for (const s of spans) {
    const parent = s.parent_span_id && ids.has(s.parent_span_id) ? s.parent_span_id : null;
    const list = byParent.get(parent) ?? [];
    list.push(s);
    byParent.set(parent, list);
  }
  for (const list of byParent.values()) {
    list.sort((a, b) => a.start_time_ns - b.start_time_ns);
  }
  const out: Node[] = [];
  const walk = (parentId: string | null, depth: number) => {
    for (const span of byParent.get(parentId) ?? []) {
      out.push({ span, depth });
      walk(span.span_id, depth + 1);
    }
  };
  walk(null, 0);
  return out;
}

export function Waterfall({ spans, selectedId, onSelect }: Props) {
  if (!spans.length) return null;
  const order = buildOrder(spans);
  const t0 = Math.min(...spans.map((s) => s.start_time_ns));
  const t1 = Math.max(...spans.map((s) => s.end_time_ns ?? s.start_time_ns));
  const span = Math.max(t1 - t0, 1);

  return (
    <div className="waterfall">
      {order.map(({ span: s, depth }) => {
        const start = ((s.start_time_ns - t0) / span) * 100;
        const end = (((s.end_time_ns ?? s.start_time_ns) - t0) / span) * 100;
        const width = Math.max(end - start, 0.5);
        return (
          <div
            key={s.span_id}
            className={`wf-row ${selectedId === s.span_id ? "selected" : ""}`}
            onClick={() => onSelect(s)}
          >
            <div className="wf-label" style={{ paddingLeft: depth * 14 }}>
              <span
                className="badge kind"
                style={{ background: kindColor(s.kind) }}
                title={s.kind}
              >
                {s.kind}
              </span>
              <span title={s.name}>{s.name}</span>
              {s.status === "error" && (
                <span
                  title="error"
                  style={{ color: "var(--danger)", fontWeight: 700 }}
                >
                  (!)
                </span>
              )}
            </div>
            <div className="wf-track">
              <div
                className="wf-bar"
                style={{
                  left: `${start}%`,
                  width: `${width}%`,
                  background: kindColor(s.kind),
                  opacity: s.status === "error" ? 0.55 : 0.9,
                }}
                title={`${fmtDuration(s.duration_ms)}`}
              />
            </div>
            <div className="wf-dur">{fmtDuration(s.duration_ms)}</div>
          </div>
        );
      })}
    </div>
  );
}
