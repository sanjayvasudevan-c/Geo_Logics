"""Reusable evaluation harness — scores any answer producer against any annotation split.

Deliberately agnostic about *what* produces an answer. The same harness scores the S8 oracle
(M2 on ground-truth maps), the blind and majority baselines, and later the full predicted
pipeline at S13 — so the numbers are comparable by construction rather than by care.

Two reporting rules are baked in rather than left to the caller:

- **Abstentions are counted separately, never as wrong.** A parser that declines to guess is a
  different failure from a geometry engine that computes the wrong number, and conflating them
  would hide which one to fix. Both a strict accuracy (abstention = wrong) and an
  attempted-only accuracy are reported.
- **Bootstrap confidence intervals resample over patches, not annotations.** Annotations within
  a patch are correlated — several questions are asked about the same image — so resampling
  them independently produces intervals that are too narrow (IMPLEMENTATION_MAP §8.3).
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Scored", "TaskScore", "bootstrap_ci", "score_task"]


@dataclass(frozen=True)
class Scored:
    """One scored item."""

    patch_id: str
    task: str
    predicted: str | None      # None means the producer abstained
    truth: str
    correct: bool
    abstained: bool
    reason: str = ""


@dataclass(frozen=True)
class TaskScore:
    """Accuracy for one task type, with abstentions separated out."""

    task: str
    n: int
    n_attempted: int
    n_correct: int
    n_abstained: int
    ci_low: float = 0.0
    ci_high: float = 0.0
    abstain_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def strict_accuracy(self) -> float:
        """Abstentions counted as wrong. The number that must be reported as headline."""
        return self.n_correct / self.n if self.n else 0.0

    @property
    def attempted_accuracy(self) -> float:
        """Accuracy over items the producer actually attempted."""
        return self.n_correct / self.n_attempted if self.n_attempted else 0.0

    @property
    def abstain_rate(self) -> float:
        return self.n_abstained / self.n if self.n else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task, "n": self.n, "n_attempted": self.n_attempted,
            "n_correct": self.n_correct, "n_abstained": self.n_abstained,
            "strict_accuracy": round(self.strict_accuracy, 4),
            "attempted_accuracy": round(self.attempted_accuracy, 4),
            "abstain_rate": round(self.abstain_rate, 4),
            "ci95_low": round(self.ci_low, 4), "ci95_high": round(self.ci_high, 4),
            "abstain_reasons": dict(sorted(
                self.abstain_reasons.items(), key=lambda kv: -kv[1])[:8]),
        }


def bootstrap_ci(
    items: list[Scored], *, resamples: int = 1000, seed: int = 1337, level: float = 0.95
) -> tuple[float, float]:
    """Bootstrap CI for strict accuracy, resampling over **patches**.

    Resampling annotations independently would understate the interval, because several
    questions share an image and their outcomes are correlated.
    """
    if not items:
        return (0.0, 0.0)
    by_patch: dict[str, list[Scored]] = defaultdict(list)
    for it in items:
        by_patch[it.patch_id].append(it)
    patches = list(by_patch)
    rng = random.Random(seed)
    accs: list[float] = []
    for _ in range(resamples):
        picked = [patches[rng.randrange(len(patches))] for _ in range(len(patches))]
        hit = total = 0
        for p in picked:
            for it in by_patch[p]:
                total += 1
                hit += int(it.correct)
        if total:
            accs.append(hit / total)
    if not accs:
        return (0.0, 0.0)
    accs.sort()
    lo = accs[int((1 - level) / 2 * len(accs))]
    hi = accs[min(int((1 + level) / 2 * len(accs)), len(accs) - 1)]
    return (lo, hi)


def score_task(task: str, items: list[Scored], *, resamples: int = 1000) -> TaskScore:
    """Aggregate scored items for one task type."""
    reasons: dict[str, int] = defaultdict(int)
    for it in items:
        if it.abstained:
            reasons[it.reason] += 1
    lo, hi = bootstrap_ci(items, resamples=resamples)
    return TaskScore(
        task=task,
        n=len(items),
        n_attempted=sum(1 for i in items if not i.abstained),
        n_correct=sum(1 for i in items if i.correct),
        n_abstained=sum(1 for i in items if i.abstained),
        ci_low=lo, ci_high=hi, abstain_reasons=dict(reasons),
    )
