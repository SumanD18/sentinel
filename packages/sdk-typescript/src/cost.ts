// Token cost estimation. Prices in USD per 1K tokens; override via registerPricing.

import type { TokenUsage } from "./types.js";

interface ModelPrice {
  prompt: number;
  completion: number;
}

const PRICING: Record<string, ModelPrice> = {
  "gpt-4o": { prompt: 0.0025, completion: 0.01 },
  "gpt-4o-mini": { prompt: 0.00015, completion: 0.0006 },
  "gpt-4-turbo": { prompt: 0.01, completion: 0.03 },
  "gpt-4": { prompt: 0.03, completion: 0.06 },
  "gpt-3.5-turbo": { prompt: 0.0005, completion: 0.0015 },
  o1: { prompt: 0.015, completion: 0.06 },
  "claude-3-5-sonnet": { prompt: 0.003, completion: 0.015 },
  "claude-3-5-haiku": { prompt: 0.0008, completion: 0.004 },
  "claude-3-opus": { prompt: 0.015, completion: 0.075 },
  "claude-3-haiku": { prompt: 0.00025, completion: 0.00125 },
};

export function registerPricing(model: string, promptPer1k: number, completionPer1k: number): void {
  PRICING[model] = { prompt: promptPer1k, completion: completionPer1k };
}

function lookup(model: string): ModelPrice | null {
  if (PRICING[model]) return PRICING[model];
  // Longest matching prefix, so dated ids (gpt-4o-2024-08-06) still resolve.
  let best: string | null = null;
  for (const known of Object.keys(PRICING)) {
    if (model.startsWith(known) && (best === null || known.length > best.length)) {
      best = known;
    }
  }
  return best ? PRICING[best] : null;
}

export function estimateCost(model: string | null, usage: TokenUsage | null): number | null {
  if (!model || !usage) return null;
  const price = lookup(model);
  if (!price) return null;
  const cost =
    (usage.prompt_tokens / 1000) * price.prompt +
    (usage.completion_tokens / 1000) * price.completion;
  return Math.round(cost * 1e8) / 1e8;
}
