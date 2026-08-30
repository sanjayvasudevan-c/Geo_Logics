"""M10 fallback classifier: task->intent mapping, fitting, persistence, and its guardrails.

Training corpora here are SYNTHETIC (CLAUDE.md §7) — short invented questions with known labels,
sufficient to exercise fit/predict/save/load without reading the annotation store.

The real accuracy measurement lives in `scripts/evaluate_parser.py` and is reported on the
validation split; nothing here should be read as an accuracy claim.
"""

from __future__ import annotations

import pytest

from satquery.exceptions import ModelError, RoutingError
from satquery.routing import TASK_TO_INTENT, Intent, M10Classifier, task_to_intent

pytestmark = pytest.mark.unit


class TestTaskToIntent:
    def test_all_fifteen_measured_tasks_are_mapped(self) -> None:
        """S3 measured the task space as closed at 15 (type, category) pairs."""
        assert len(TASK_TO_INTENT) == 15

    def test_the_three_metadata_categories_collapse_to_one_intent(self) -> None:
        """They share one tool plan (M5 -> M4 -> M9); distinguishing them is M5's job."""
        got = {task_to_intent("mcq", c) for c in ("country", "season", "climate zone")}
        assert got == {Intent.METADATA_MCQ}

    def test_binary_and_mcq_of_the_same_category_share_an_intent(self) -> None:
        for cat in ("presence", "area", "count", "adjacency"):
            assert task_to_intent("binary", cat) is task_to_intent("mcq", cat)

    def test_the_two_bounding_box_tasks_stay_distinct(self) -> None:
        """They take different inputs — a <ref> tag vs a <point> coordinate — so the parser
        must keep them apart even though S10 routes them through the same plan."""
        assert task_to_intent("bounding box", "reference") is Intent.REFERRING_EXPR
        assert task_to_intent("bounding box", "point") is Intent.REFERRING_POINT

    def test_the_observed_label_space_is_nine_intents(self) -> None:
        """MEASURED, and it closes assumption A5.

        15 tasks collapse onto 9 intents. CHANGE is the 10th enum value and has no rows in
        this benchmark. CLAUDE.md §1 describes M10 as "8-way", which predates S3 measuring the
        real vocabulary; see DECISIONS.md D-S9-1.
        """
        assert len(set(TASK_TO_INTENT.values())) == 9
        assert Intent.CHANGE not in set(TASK_TO_INTENT.values())

    def test_an_unknown_task_raises_rather_than_defaulting(self) -> None:
        """A silent default would route a novel task somewhere plausible and wrong."""
        with pytest.raises(RoutingError) as exc:
            task_to_intent("mcq", "elevation")
        assert exc.value.context["category"] == "elevation"


@pytest.fixture
def corpus() -> tuple[list[str], list[Intent]]:
    """SYNTHETIC training corpus with three clearly separable intents."""
    q, y = [], []
    for i in range(12):
        q.append(f"how many separate patches of forest number {i}")
        y.append(Intent.COUNT)
        q.append(f"what percentage of the image is covered by water {i}")
        y.append(Intent.AREA)
        q.append(f"describe this satellite scene in detail {i}")
        y.append(Intent.CAPTION)
    return q, y


class TestFitAndPredict:
    def test_it_fits_and_recovers_its_own_training_intents(self, corpus) -> None:
        q, y = corpus
        m = M10Classifier.fit(q, y)
        assert set(m.labels) == {"count", "area", "caption"}
        assert m.predict(q) == y

    def test_it_predicts_on_unseen_wording(self, corpus) -> None:
        q, y = corpus
        m = M10Classifier.fit(q, y)
        assert m.predict(["how many separate patches of grassland are visible"]) == [Intent.COUNT]

    def test_empty_input_predicts_nothing(self, corpus) -> None:
        q, y = corpus
        assert M10Classifier.fit(q, y).predict([]) == []

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ModelError):
            M10Classifier.fit(["a", "b"], [Intent.COUNT])

    def test_no_training_data_raises(self) -> None:
        with pytest.raises(ModelError):
            M10Classifier.fit([], [])

    def test_a_single_class_raises_rather_than_scoring_a_perfect_nothing(self) -> None:
        """A one-class "classifier" reports 100% while having learned nothing."""
        with pytest.raises(ModelError) as exc:
            M10Classifier.fit([f"q{i}" for i in range(10)], [Intent.COUNT] * 10)
        assert exc.value.context["n_classes"] == 1


class TestProvenanceAndPersistence:
    def test_the_manifest_records_what_it_was_trained_on(self, corpus) -> None:
        """CLAUDE.md §8: every saved model records its provenance."""
        q, y = corpus
        man = M10Classifier.fit(q, y).manifest
        assert man["n_train"] == len(q)
        assert man["seed"] == 1337
        assert man["trained_on"] == "train split only"
        assert len(man["train_split_hash"]) == 16

    def test_a_different_training_corpus_changes_the_hash(self, corpus) -> None:
        q, y = corpus
        a = M10Classifier.fit(q, y).manifest["train_split_hash"]
        b = M10Classifier.fit(q[:-3], y[:-3]).manifest["train_split_hash"]
        assert a != b

    def test_round_trip_preserves_predictions(self, corpus, tmp_path) -> None:
        q, y = corpus
        m = M10Classifier.fit(q, y)
        path = tmp_path / "m10.joblib"
        m.save(path)
        assert M10Classifier.load(path).predict(q) == m.predict(q)

    def test_saving_writes_a_readable_manifest_beside_the_model(self, corpus, tmp_path) -> None:
        import json
        q, y = corpus
        path = tmp_path / "m10.joblib"
        M10Classifier.fit(q, y).save(path)
        side = json.loads(path.with_suffix(".manifest.json").read_text("utf-8"))
        assert side["model"].startswith("TfidfVectorizer")

    def test_loading_a_missing_artifact_raises(self, tmp_path) -> None:
        with pytest.raises(ModelError):
            M10Classifier.load(tmp_path / "nope.joblib")

    def test_fitting_is_deterministic_for_a_fixed_seed(self, corpus) -> None:
        q, y = corpus
        probe = ["how many distinct regions of forest", "describe the scene"]
        assert M10Classifier.fit(q, y, seed=7).predict(probe) == \
            M10Classifier.fit(q, y, seed=7).predict(probe)
