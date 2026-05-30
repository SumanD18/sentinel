# sentinel-evaluators

Local-first hallucination and anomaly evaluators for LLM outputs. Part of
[Sentinel](https://github.com/SumanD18/sentinel).

The default suite runs **without any external model or network call**, so it's
safe to execute inline during trace ingestion. Heavier, model-based evaluators
(semantic similarity via `sentence-transformers`) activate automatically when the
optional dependency is installed.

## Install

```bash
pip install sentinel-evaluators
pip install "sentinel-evaluators[embeddings]"   # adds semantic similarity
```

## Use

```python
from sentinel_evaluators import EvalInput, run_suite, aggregate_score

results = run_suite(EvalInput(
    output="The Eiffel Tower is in Berlin.",
    context=["Paris is the capital of France and home to the Eiffel Tower."],
))
for r in results:
    print(r.evaluator, r.score, r.verdict, "-", r.explanation)

print("trust:", aggregate_score(results))   # blends weakest + mean
```

## Built-in evaluators

| Name | Signal |
| --- | --- |
| `confidence` | hedging / low-confidence language |
| `groundedness` | answer-vs-context overlap (RAG hallucination signal) |
| `repetition` | degenerate / looping output |
| `refusal` | refusal detection |
| `non_empty` | empty / too-short output |
| `factuality_smoke` | fabricated citations, impossible dates |
| `self_consistency` | agreement across resampled completions |
| `semantic_drift` | similarity to a reference answer |

Register your own with `sentinel_evaluators.register(name, factory)`.

## Offline eval runner

```python
from sentinel_evaluators import run_eval, load_dataset

report = run_eval(
    name="qa", model="gpt-4o",
    dataset=load_dataset("cases.jsonl"),
    generate=lambda case: my_model(case["prompt"]),
)
print(report.to_markdown())
```

## License

Apache 2.0.
