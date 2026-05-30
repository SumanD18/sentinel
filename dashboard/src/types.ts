// Shared types mirroring the server's response schemas.

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface EvalResult {
  evaluator: string;
  score: number;
  verdict: "pass" | "warn" | "fail";
  explanation: string;
  details: Record<string, unknown>;
}

export interface Span {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  kind: string;
  status: string;
  status_message: string | null;
  start_time_ns: number;
  end_time_ns: number | null;
  duration_ms: number | null;
  model: string | null;
  provider: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  input: unknown;
  output: unknown;
  attributes: Record<string, unknown>;
  events: unknown[];
  eval_results: EvalResult[] | null;
  trust_score: number | null;
}

export interface TraceSummary {
  trace_id: string;
  service_name: string;
  environment: string;
  root_name: string | null;
  status: string;
  duration_ms: number | null;
  span_count: number;
  llm_call_count: number;
  total_tokens: number;
  total_cost_usd: number;
  min_trust_score: number;
  has_alert: boolean;
  created_at: string;
}

export interface TraceDetail extends TraceSummary {
  spans: Span[];
}

export interface Alert {
  id: number;
  trace_id: string;
  span_id: string | null;
  rule: string;
  severity: "info" | "warning" | "critical";
  message: string;
  details: Record<string, unknown> | null;
  resolved: boolean;
  created_at: string;
}

export interface StatsOverview {
  total_traces: number;
  total_spans: number;
  total_llm_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  open_alerts: number;
  mean_trust_score: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  cost_by_model: Record<string, number>;
  calls_by_provider: Record<string, number>;
}

export interface Prompt {
  id: number;
  name: string;
  version: number;
  template: string;
  description: string | null;
  variables: string[];
  meta: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}
