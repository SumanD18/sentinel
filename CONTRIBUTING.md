# Contributing to Sentinel

First off, thank you. Sentinel is built by people who got tired of debugging AI
systems blind, and every contribution makes it better for the next person.

This guide gets you from zero to a green test run, then points you at good first
issues. **No cloud account, no API keys, and no paid services are required to
develop or test Sentinel.**

## TL;DR

```bash
git clone https://github.com/SumanD18/sentinel.git
cd sentinel

# Backend + SDK + evaluators
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e packages/evaluators
pip install -e "packages/sdk-python[dev]"
pip install -e "server[dev]"

# Run the test suites (all should pass)
pytest packages/sdk-python packages/evaluators server

# Dashboard
cd dashboard && npm install && npm run build
```

## Project layout & where things live

| Path | What it is | Language |
| --- | --- | --- |
| `packages/sdk-python/` | The SDK: `wrap()`, `trace()`, `span()`, exporters, wrappers | Python |
| `packages/evaluators/` | Local-first trust/hallucination evaluators | Python |
| `server/` | FastAPI collector, ingestion, storage, API, metrics | Python |
| `dashboard/` | React + TypeScript UI (Vite, Recharts) | TypeScript |
| `examples/` | Runnable integration examples | Python |
| `evals/` | Eval datasets + the CI-gated runner | Python |

The three Python packages are independent and installable on their own. The
server depends on `evaluators`; the SDK depends on **nothing** (stdlib only) by
design - keep it that way.

## Running things locally

**The full stack:**

```bash
docker compose up --build      # dashboard :3000, collector :8000
```

**Just the server (with live reload):**

```bash
pip install -e packages/evaluators -e "server[dev]"
sentinel-server --reload
```

**Just the dashboard (proxies the API to :8000):**

```bash
cd dashboard && npm run dev      # http://localhost:5173
```

**Seed demo data (no keys):**

```bash
pip install -e packages/sdk-python
python examples/quickstart/seed_demo.py
```

## How we work

1. **Open an issue first** for anything non-trivial, so we can agree on the
   approach before you spend time on it.
2. **Branch** from `main`: `git checkout -b fix/streaming-usage`.
3. **Write a test.** Every bug fix gets a regression test; every feature gets
   coverage. The test suites are fast and run offline.
4. **Keep the SDK dependency-free.** If you need a heavy library, it belongs in
   the server or behind an optional `extras` group.
5. **Run the checks** before pushing:
   ```bash
   ruff check packages server          # lint
   mypy packages/sdk-python/sentinel   # types
   pytest packages server              # tests
   cd dashboard && npm run lint && npm run build
   ```
6. **Open a PR.** Describe what changed and why. CI runs lint, types, tests,
   Docker build, and the eval gate on every PR.

## Code style

- **Python:** [ruff](https://docs.astral.sh/ruff/) for lint + import order, type
  hints everywhere, Google-ish docstrings on public functions. Target 3.9 for the
  SDK, 3.10+ for the server.
- **TypeScript:** strict mode is on; no `any` in component props; keep components
  small and the API layer in `src/api.ts`.
- Match the surrounding code. Comments explain *why*, not *what*.

## Writing a new evaluator

Evaluators are the easiest high-impact contribution. Subclass `Evaluator`,
implement `evaluate`, and register it:

```python
from sentinel_evaluators.base import EvalInput, EvalResult, Evaluator
from sentinel_evaluators.registry import register

class ProfanityEvaluator(Evaluator):
    name = "profanity"
    def evaluate(self, item: EvalInput) -> EvalResult:
        bad = count_profanity(item.output)
        return self._result(1.0 if bad == 0 else 0.0, f"{bad} flagged terms")

register("profanity", ProfanityEvaluator)
```

Add a test in `packages/evaluators/tests/` and you're done.

## Writing a new guardrail

Guardrails live in `server/sentinel_server/guardrails.py`. A guardrail is a
function `(span, eval_results, trust_score) -> list[AlertSpec]`. Register it and
add a test in `server/tests/`.

## Good first issues

Look for the [`good first issue`](https://github.com/SumanD18/sentinel/labels/good%20first%20issue)
label. Some perennial favourites:

- Add a provider wrapper (Gemini, Cohere, Mistral).
- Add an evaluator (toxicity, JSON-schema-validity, language detection).
- Improve the cost table or make it auto-update from a config file.
- Dashboard polish: keyboard navigation in the waterfall, dark/light toggle.

## Code of Conduct

Be kind, be constructive, assume good faith. We follow the
[Contributor Covenant](https://www.contributor-covenant.org/). Report issues to
the maintainers via a private GitHub message.

## License

By contributing, you agree that your contributions are licensed under the
[Apache 2.0 License](LICENSE).
