# Evals

Run automated evaluation suites against your own datasets - offline (scoring
recorded outputs) or live (regenerating with a model). The same scorer powers
the inline trust scores you see in the dashboard, so CI and production agree.

## Run

```bash
# Offline - deterministic, no API keys (used in CI)
python evals/run_evals.py --dataset evals/datasets/factual_qa.jsonl

# Live - regenerate with a model and score the fresh outputs
export OPENAI_API_KEY=sk-...
python evals/run_evals.py --dataset evals/datasets/factual_qa.jsonl \
    --provider openai --model gpt-4o-mini
```

Reports are written to `evals/reports/{name}.json` and `.md`. The process exits
non-zero when the pass rate falls below `--min-pass-rate`, so it works as a CI
gate (see [`.github/workflows/evals.yml`](../.github/workflows/evals.yml)).

## Dataset format

JSON or JSONL, one case per line:

```json
{"id": "capital-france", "prompt": "What is the capital of France?",
 "reference": "Paris", "output": "The capital of France is Paris.",
 "context": ["France's capital is Paris."]}
```

| Field | Used by | Notes |
| --- | --- | --- |
| `prompt` | live generation | the question/instruction |
| `context` | `groundedness` | retrieved docs; enables hallucination scoring |
| `reference` | `semantic_drift` | gold answer for drift comparison |
| `output` | offline mode | the recorded answer to score |

## A note on the default (model-free) evaluators

The built-in suite is **local-first**: it uses regex + bag-of-words heuristics so
it can run inline on every span with no external calls. That catches hedging,
refusals, repetition, empty answers, and lexical groundedness very cheaply, but
it cannot detect a *semantic* contradiction that happens to reuse the context's
vocabulary. For that, install the optional embedding evaluator:

```bash
pip install "sentinel-evaluators[embeddings]"
```

`semantic_drift` and `self_consistency` then use `sentence-transformers` for
true semantic similarity instead of word overlap.
