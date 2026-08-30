"""M10 — TF-IDF -> Linear SVM fallback intent classifier.

Fires **only** when the Q1 rule parser declines. Closed-set classification over a vocabulary S3
measured exhaustively, so an SVM is the right tool: it is cheap, CPU-only, deterministic, and
auditable. CLAUDE.md §1 and the S9 stage prompt both forbid substituting a language model here,
and a language model would in any case be the wrong shape — it cannot be inspected for *why* it
routed a question, which is the property the deterministic router depends on.

**M10 predicts an intent, never an answer.** CLAUDE.md §2's number-flow rule is unaffected: the
value still comes from `M1 -> M2 -> NUMBER`. Being wrong here routes a question to the wrong
tool; it cannot fabricate a quantity.

Trained on the **training** annotation split only, and persisted with the training-split hash so
a model fitted on different data cannot be loaded silently against the wrong split.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]  # ships no py.typed marker
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from satquery.exceptions import ModelError, RoutingError
from satquery.routing.parser import Intent
from satquery.utils.hashing import hash_bytes

__all__ = ["M10Classifier", "TrainedM10", "task_to_intent"]

#: The 15 measured ``type``/``category`` tasks (S3 §1) collapsed onto routing intents.
#: Three metadata categories share one intent because they share one tool plan (M5 -> M4 -> M9);
#: the distinction between country, season and climate is M5's to make, not the router's.
TASK_TO_INTENT: dict[tuple[str, str], Intent] = {
    ("binary", "presence"): Intent.PRESENCE,
    ("binary", "area"): Intent.AREA,
    ("binary", "count"): Intent.COUNT,
    ("binary", "adjacency"): Intent.ADJACENCY,
    ("mcq", "presence"): Intent.PRESENCE,
    ("mcq", "area"): Intent.AREA,
    ("mcq", "count"): Intent.COUNT,
    ("mcq", "adjacency"): Intent.ADJACENCY,
    ("mcq", "relative pos"): Intent.RELATIVE_POSITION,
    ("mcq", "country"): Intent.METADATA_MCQ,
    ("mcq", "season"): Intent.METADATA_MCQ,
    ("mcq", "climate zone"): Intent.METADATA_MCQ,
    ("captioning", "None"): Intent.CAPTION,
    ("bounding box", "reference"): Intent.REFERRING_EXPR,
    ("bounding box", "point"): Intent.REFERRING_POINT,
}


def task_to_intent(task_type: str, category: str) -> Intent:
    """Map a measured ``(type, category)`` pair to its routing intent.

    Raises:
        RoutingError: If the pair is not one of the 15 S3 measured it. An unknown task must
            surface rather than fall through to a default — CLAUDE.md §1 freezes the task space,
            so a new pair means the data changed and that is worth stopping for.
    """
    key = (str(task_type), str(category))
    if key not in TASK_TO_INTENT:
        raise RoutingError("unknown task; the S3 task space is closed at 15",
                           task_type=task_type, category=category)
    return TASK_TO_INTENT[key]


@dataclass(frozen=True)
class TrainedM10:
    """A fitted M10 plus the provenance needed to trust it (CLAUDE.md §8)."""

    pipeline: Pipeline
    labels: tuple[str, ...]
    n_train: int
    train_split_hash: str
    seed: int

    def to_manifest(self) -> dict[str, Any]:
        return {"labels": list(self.labels), "n_train": self.n_train,
                "train_split_hash": self.train_split_hash, "seed": self.seed,
                "model": "TfidfVectorizer(1,2) -> LinearSVC", "trained_on": "train split only"}


class M10Classifier:
    """Fallback intent classifier. Fits, persists, loads, predicts."""

    def __init__(self, trained: TrainedM10) -> None:
        self._t = trained

    @property
    def labels(self) -> tuple[str, ...]:
        return self._t.labels

    @property
    def manifest(self) -> dict[str, Any]:
        return self._t.to_manifest()

    @classmethod
    def fit(cls, questions: list[str], intents: list[Intent], *, seed: int = 1337
            ) -> M10Classifier:
        """Fit on training-split questions.

        Raises:
            ModelError: If there is nothing to fit, or only one class is present — a
                single-class "classifier" would report a perfect score while learning nothing.
        """
        if not questions or len(questions) != len(intents):
            raise ModelError("M10 needs matching questions and intents",
                             n_questions=len(questions), n_intents=len(intents))
        y = [i.value for i in intents]
        if len(set(y)) < 2:
            raise ModelError("M10 needs at least two intents to fit", n_classes=len(set(y)))
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                      max_features=200_000, strip_accents="unicode")),
            ("svm", LinearSVC(C=1.0, max_iter=5000, random_state=seed)),
        ])
        pipe.fit(questions, y)
        return cls(TrainedM10(
            pipeline=pipe, labels=tuple(sorted(set(y))), n_train=len(questions),
            train_split_hash=hash_bytes("\n".join(questions).encode("utf-8"))[:16], seed=seed,
        ))

    def predict(self, questions: list[str]) -> list[Intent]:
        """Predict an intent per question."""
        if not questions:
            return []
        return [Intent(v) for v in self._t.pipeline.predict(questions)]

    def save(self, path: Path) -> None:
        """Persist the fitted vectorizer + model together with its manifest."""
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._t, path)
        path.with_suffix(".manifest.json").write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> M10Classifier:
        """Load a persisted M10.

        Raises:
            ModelError: If the artifact is missing.
        """
        if not path.is_file():
            raise ModelError("no persisted M10 found", path=str(path))
        return cls(joblib.load(path))
