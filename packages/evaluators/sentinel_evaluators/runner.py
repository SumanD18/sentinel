"""Offline eval-suite runner for CI and head-to-head model comparison.

Reads a dataset (list of cases), runs a generation callback per case, scores the
output with a set of evaluators, and produces a structured report plus markdown
suitable for a CI job summary.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .base import EvalInput, EvalResult
from .registry import aggregate_score, run_suite

#: A generation function: takes the case dict, returns the model output text.
GenerateFn = Callable[[dict], str]


@dataclass
class CaseResult:
    case_id: str
    prompt: str
    output: str
    trust_score: float
    results: list[EvalResult]
    passed: bool

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "output": self.output,
            "trust_score": self.trust_score,
            "passed": self.passed,
            "evaluators": [r.to_dict() for r in self.results],
        }


@dataclass
class EvalReport:
    name: str
    model: str
    cases: list[CaseResult] = field(default_factory=list)
    pass_threshold: float = 0.6

    @property
    def mean_trust(self) -> float:
        if not self.cases:
            return 0.0
        return round(statistics.mean(c.trust_score for c in self.cases), 4)

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return round(sum(c.passed for c in self.cases) / len(self.cases), 4)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "mean_trust": self.mean_trust,
            "pass_rate": self.pass_rate,
            "pass_threshold": self.pass_threshold,
            "cases": [c.to_dict() for c in self.cases],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Eval report: {self.name}",
            "",
            f"- **Model:** `{self.model}`",
            f"- **Cases:** {len(self.cases)}",
            f"- **Mean trust score:** {self.mean_trust:.3f}",
            f"- **Pass rate:** {self.pass_rate:.1%} (threshold {self.pass_threshold})",
            "",
            "| Case | Trust | Passed | Weakest dimension |",
            "| --- | --- | --- | --- |",
        ]
        for c in self.cases:
            weakest = min(c.results, key=lambda r: r.score, default=None)
            wk = f"{weakest.evaluator} ({weakest.score:.2f})" if weakest else "-"
            lines.append(
                f"| {c.case_id} | {c.trust_score:.2f} | "
                f"{'PASS' if c.passed else 'FAIL'} | {wk} |"
            )
        return "\n".join(lines) + "\n"


def load_dataset(path: str | Path) -> list[dict]:
    """Load a dataset from JSON or JSONL."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    return data["cases"] if isinstance(data, dict) and "cases" in data else data


def run_eval(
    name: str,
    model: str,
    dataset: list[dict],
    generate: GenerateFn,
    evaluators: list[str] | None = None,
    pass_threshold: float = 0.6,
) -> EvalReport:
    """Run an eval suite. Each dataset case supports keys: ``id``, ``prompt``,
    ``context``, ``reference``."""
    report = EvalReport(name=name, model=model, pass_threshold=pass_threshold)
    for i, case in enumerate(dataset):
        prompt = case.get("prompt", "")
        output = generate(case)
        item = EvalInput(
            output=output,
            prompt=prompt,
            context=case.get("context"),
            reference=case.get("reference"),
        )
        results = run_suite(item, evaluators)
        trust = aggregate_score(results)
        report.cases.append(
            CaseResult(
                case_id=str(case.get("id", i)),
                prompt=prompt,
                output=output,
                trust_score=trust,
                results=results,
                passed=trust >= pass_threshold,
            )
        )
    return report
