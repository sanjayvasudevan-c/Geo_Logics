"""Oracle relative-position path: option parsing, subject orientation, end-to-end direction.

All class maps are SYNTHETIC (CLAUDE.md §7) with the answer known by construction.

This file exists because S8 shipped ``oracle.py`` with **no unit tests**, and two defects rode
along undetected until GATE 1 measured them:

1. ``option_direction`` matched a single compass letter as a *substring*, so a computed ``SE``
   selected the option "bottom-left" because ``"S" in "SE"``. Worth +10.00 points.
2. The parser read the first-mentioned class as the subject for every template, but 25.96% of
   stems invert that. Worth far more — the reversed reading scores a forced 0.00%.

Both are asserted here directly, so neither can return silently.
"""

from __future__ import annotations

import numpy as np
import pytest

from satquery.config import load_config
from satquery.evaluation.oracle import (
    OracleAnswer,
    ParseFailure,
    answer_question,
    option_direction,
    subject_is_second,
)
from satquery.geometry import GeometryParams
from satquery.taxonomy import load_synonyms, load_taxonomy

pytestmark = pytest.mark.unit

URBAN, ARABLE, WATER = 112, 211, 512


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


@pytest.fixture(scope="module")
def syn():
    return load_synonyms()


@pytest.fixture(scope="module")
def cfg():
    return load_config().m2


@pytest.fixture(scope="module")
def params(cfg):
    return GeometryParams.from_config(cfg, gsd_m=10.0)


def _map(urban_at: tuple[slice, slice], water_at: tuple[slice, slice]) -> np.ndarray:
    """Arable background with one urban block and one water block at known positions."""
    grid = np.full((60, 60), ARABLE, dtype=np.int32)
    grid[urban_at] = URBAN
    grid[water_at] = WATER
    return grid


class TestOptionDirection:
    @pytest.mark.parametrize(
        ("text", "want"),
        [("to the top-left", "NW"), ("to the bottom-left", "SW"),
         ("to the top-right", "NE"), ("to the bottom-right", "SE"),
         ("to the top", "N"), ("to the bottom", "S"),
         ("to the left", "W"), ("to the right", "E")],
    )
    def test_every_released_option_phrase_parses(self, text, want) -> None:
        assert option_direction(text) == want

    def test_compound_beats_its_own_prefix(self) -> None:
        """"bottom-left" must be SW, never S — the compound has to be consumed first."""
        assert option_direction("to the bottom-left") == "SW"
        assert option_direction("to the bottom") == "S"

    def test_a_non_direction_option_is_none_not_a_guess(self) -> None:
        assert option_direction("to the arable land") is None


class TestSubjectOrientation:
    @pytest.mark.parametrize("stem", [
        "Using the pastures as the reference, how would you describe the position of the "
        "arable land?",
        "Considering the pastures as a reference, where does the arable land appear?",
        "Relative to the pastures, where does the arable land appear in the scene?",
        "In relation to the pastures, where is the arable land located in the image?",
        "What is the spatial direction from the pastures to the arable land?",
    ])
    def test_inverting_templates_are_detected(self, stem) -> None:
        assert subject_is_second(stem) is True

    @pytest.mark.parametrize("stem", [
        "What is the relative position of the pastures to the arable land?",
        "How would you describe the relative location of the pastures to the arable land?",
        "What directional relationship exists between the pastures and the arable land?",
        "Where is the pastures located compared with the arable land?",
        "How does the pastures spatially relate to the arable land in this image?",
    ])
    def test_normal_templates_are_not_flipped(self, stem) -> None:
        assert subject_is_second(stem) is False

    def test_an_option_cannot_trigger_the_flip(self) -> None:
        """Only the stem is inspected, so "relative to" inside an option is inert."""
        q = ("What is the relative position of the pastures to the arable land? "
             "a) to the top relative to the centre, b) to the bottom, "
             "c) to the left, d) to the right")
        assert subject_is_second(q) is False


class TestEndToEndDirection:
    """Urban is placed due NORTH of water; the answer must follow the template's orientation."""

    OPTS = "a) to the top, b) to the bottom, c) to the left, d) to the right"

    @pytest.fixture
    def north_map(self):
        return _map((slice(5, 15), slice(25, 35)), (slice(45, 55), slice(25, 35)))

    def test_normal_template_answers_subject_relative_to_reference(
        self, north_map, tax, syn, params, cfg
    ) -> None:
        q = (f"What is the relative position of the urban fabric to the inland waters? "
             f"{self.OPTS}")
        got = answer_question(north_map, q, "mcq|relative pos", tax, syn, params, cfg)
        assert isinstance(got, OracleAnswer)
        assert got.detail["direction"] == "N"
        assert got.answer == "a"

    def test_inverting_template_answers_the_other_way_round(
        self, north_map, tax, syn, params, cfg
    ) -> None:
        """Same map, same options — only the wording inverts, so the answer must too.

        This is the assertion the S8 parser would have failed. Urban is north of water, so
        asking where the WATER is, using urban as the reference, must answer "to the bottom".
        """
        q = (f"Using the urban fabric as the reference, how would you describe the position "
             f"of the inland waters? {self.OPTS}")
        got = answer_question(north_map, q, "mcq|relative pos", tax, syn, params, cfg)
        assert isinstance(got, OracleAnswer)
        assert got.detail["direction"] == "S"
        assert got.answer == "b"

    def test_the_two_orientations_disagree(self, north_map, tax, syn, params, cfg) -> None:
        """Guards the whole point: if these ever agree, the flip has stopped working."""
        normal = answer_question(
            north_map,
            f"What is the relative position of the urban fabric to the inland waters? "
            f"{self.OPTS}",
            "mcq|relative pos", tax, syn, params, cfg,
        )
        inverted = answer_question(
            north_map,
            f"Relative to the urban fabric, where do the inland waters appear in the scene? "
            f"{self.OPTS}",
            "mcq|relative pos", tax, syn, params, cfg,
        )
        assert isinstance(normal, OracleAnswer) and isinstance(inverted, OracleAnswer)
        assert normal.answer != inverted.answer

    def test_a_shallow_diagonal_reads_cardinal_under_the_fitted_band(
        self, tax, syn, params, cfg
    ) -> None:
        """Urban 30 rows north and 10 cols east of water: a bearing of ~18 degrees.

        The textbook 45-degree compass calls that NE. The fitted 16-degree band calls it N,
        and the released answers say cardinal 81.60% of the time. Asserted on the answer, not
        on the band value, so it survives any re-fit inside the indistinguishable range.
        """
        grid = _map((slice(10, 20), slice(30, 40)), (slice(40, 50), slice(20, 30)))
        q = ("What is the relative position of the urban fabric to the inland waters? "
             "a) to the top, b) to the top-right, c) to the bottom, d) to the left")
        got = answer_question(grid, q, "mcq|relative pos", tax, syn, params, cfg)
        assert isinstance(got, OracleAnswer)
        assert got.detail["direction"] == "N"
        assert got.answer == "a"

    def test_an_absent_class_abstains_rather_than_guessing(
        self, tax, syn, params, cfg
    ) -> None:
        grid = np.full((60, 60), ARABLE, dtype=np.int32)
        grid[5:15, 5:15] = URBAN
        q = (f"What is the relative position of the urban fabric to the inland waters? "
             f"{self.OPTS}")
        got = answer_question(grid, q, "mcq|relative pos", tax, syn, params, cfg)
        assert isinstance(got, ParseFailure)
        assert "absent" in got.reason
