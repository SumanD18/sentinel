"""Run a Sentinel eval suite over a dataset and emit JSON + markdown reports.

Two modes:
  * offline (default): scores the pre-recorded ``output`` field in each case -
    fully deterministic, no API keys, ideal for CI.
  * live: pass --provider openai|anthropic to (re)generate outputs with a model
    and score those instead.

Usage:
    python evals/run_evals.py --dataset evals/datasets/factual_qa.jsonl \
        --out evals/reports --fail-under 0.6

Exit code is non-zero if the pass rate drops below --min-pass-rate, so this
doubles as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the evaluators package importable when run from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "evaluators"))

from sentinel_evaluators import load_dataset, run_eval  # noqa: E402


def offline_generator(case: dict) -> str:
    """Return the case's recorded output (deterministic, no network)."""
    return case.get("output", "")


def openai_generator(model: str):
    from openai import OpenAI

    client = OpenAI()

    def generate(case: dict) -> str:
        ctx = "\n".join(case.get("context") or [])
        system = "Answer using only the context provided. If unsure, say so."
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"{system}\n\n{ctx}"},
                {"role": "user", "content": case["prompt"]},
            ],
        )
        return resp.choices[0].message.content or ""

    return generate


def main() -> int:
    # Make stdout tolerant of unicode on legacy (cp1252) consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Run Sentinel evals.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--name", default="factual-qa")
    parser.add_argument("--provider", choices=["offline", "openai"], default="offline")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--out", default="evals/reports")
    parser.add_argument("--fail-under", type=float, default=0.6, help="per-case pass threshold")
    parser.add_argument("--min-pass-rate", type=float, default=0.6, help="suite gate")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)

    if args.provider == "openai":
        generate = openai_generator(args.model)
        model_label = args.model
    else:
        generate = offline_generator
        model_label = "offline(recorded)"

    report = run_eval(
        name=args.name,
        model=model_label,
        dataset=dataset,
        generate=generate,
        pass_threshold=args.fail_under,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{args.name}.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    md = report.to_markdown()
    (out_dir / f"{args.name}.md").write_text(md, encoding="utf-8")
    print(md)

    # Append to the GitHub Actions job summary when running in CI.
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md)

    if report.pass_rate < args.min_pass_rate:
        print(
            f"::error::Pass rate {report.pass_rate:.0%} below "
            f"minimum {args.min_pass_rate:.0%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
