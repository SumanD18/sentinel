// Typed API client for the Sentinel collector.

import type {
  Alert,
  Prompt,
  StatsOverview,
  TraceDetail,
  TraceSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface TraceFilters {
  service?: string;
  status?: string;
  has_alert?: boolean;
  min_trust?: number;
  limit?: number;
  offset?: number;
}

function qs(params: Record<string, unknown>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== "",
  );
  if (!entries.length) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}

export const api = {
  overview: () => request<StatsOverview>("/api/stats/overview"),

  traces: (filters: TraceFilters = {}) =>
    request<TraceSummary[]>(`/api/traces${qs(filters as Record<string, unknown>)}`),

  trace: (id: string) => request<TraceDetail>(`/api/traces/${id}`),

  deleteTrace: (id: string) =>
    request<{ deleted: string }>(`/api/traces/${id}`, { method: "DELETE" }),

  alerts: (params: { resolved?: boolean; severity?: string; limit?: number } = {}) =>
    request<Alert[]>(`/api/alerts${qs(params as Record<string, unknown>)}`),

  resolveAlert: (id: number) =>
    request<Alert>(`/api/alerts/${id}/resolve`, { method: "POST" }),

  prompts: () => request<Prompt[]>("/api/prompts"),

  promptVersions: (name: string) =>
    request<Prompt[]>(`/api/prompts/${name}/versions`),

  rollbackPrompt: (name: string, version: number) =>
    request<Prompt>(`/api/prompts/${name}/rollback/${version}`, { method: "POST" }),
};

export { ApiError };
