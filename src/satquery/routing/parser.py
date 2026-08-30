"""Q1 — the rule-based query parser (architecture Stage 3).

Converts a question string into a typed :class:`QuerySpec`. **No language model.** The benchmark
has a closed vocabulary — S3 measured 15 ``type`` x ``category`` tasks over a 19-class
vocabulary — so closed template rules are the correct tool, and they are auditable in a way a
prompted model is not.

Every rule here is built from **phrasing S3 actually measured**, never invented:

- adjacency's nine synonyms (`touch`, `adjacent`, `border`, `next to`, `contact`, `meet`,
  `neighbour`, `abut`, `side by side`) — ANSWER_GRAMMAR §8
- the referring vocabulary: exactly two operators (`largest`, `smallest`) crossed with eight
  surface phrasings, and ~55% of referring expressions carry no qualifier at all — §10
- area in two interchangeable units, quantised to 11 deciles (144,000 m² = 10%) — §5
- count phrasings led by `exactly two`, `at least one`, `fewer than three` — §5
- MCQ options enumerated `a) ... , b) ... , c) ... , d) ...`, answer a single lowercase
  letter — §4
- `<ref>...</ref>` and `<point>(x y)</point>` input tags — §4

**On failure it returns a :class:`ParseFailure` with a reason. It never guesses.** S8 measured
what that discipline is worth: the strict/attempted gap there was *entirely* abstention rather
than wrong geometry, which made the residual diagnosable. An abstention is a fixable finding; a
guess is a silent error.

The parser does **not** receive the task label. Inferring intent from text is the whole job —
M10 exists precisely for the questions where these rules fail.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from satquery.taxonomy import SynonymTable
from satquery.taxonomy.core import Level

__all__ = [
    "AnswerFormat",
    "Intent",
    "ParseFailure",
    "QuerySpec",
    "StatedValue",
    "parse_query",
]

PATCH_AREA_M2 = 1_440_000.0


class Intent(str, Enum):
    """The routing intent. Ten values; nine are observable in BigEarthNet.txt.

    ``CHANGE`` has no rows in this benchmark — it belongs to the SECOND/CDVQA change-detection
    path (M6, S17) and is carried here so the router's registry does not have to change shape
    later. Its absence is a fact about this dataset, not a gap in the enum.
    """

    PRESENCE = "presence"
    COUNT = "count"
    AREA = "area"
    ADJACENCY = "adjacency"
    RELATIVE_POSITION = "relative_position"
    REFERRING_EXPR = "referring_expr"
    REFERRING_POINT = "referring_point"
    METADATA_MCQ = "metadata_mcq"
    CAPTION = "caption"
    CHANGE = "change"


class AnswerFormat(str, Enum):
    """Exact output shape, from ANSWER_GRAMMAR §4. Verified, not assumed."""

    YES_NO = "yes_no"              # exactly `yes` | `no`, lowercase, no punctuation
    MCQ_LETTER = "mcq_letter"      # a single lowercase letter a|b|c|d
    BBOX = "bbox"                  # `[x0 y0, x1 y1]`, normalised to [0,1]
    FREE_TEXT = "free_text"        # captions, up to 2,265 chars


class StatedValue(BaseModel):
    """A quantity stated in the question, normalised to percent of patch area.

    S3 measured area in two interchangeable units, both quantised to 11 deciles. Normalising at
    the parser boundary means no downstream component has to know which unit was used, and no
    number is re-derived twice with different rounding.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw: str
    unit: Literal["percent", "m2", "count"]
    value: float
    as_percent: float | None = None


class QuerySpec(BaseModel):
    """The typed structure every downstream component consumes.

    CLAUDE.md §2: components exchange typed structures, never natural language. This is the
    boundary object between the parser and the router.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent: Intent
    answer_format: AnswerFormat
    clc_level: Level = "c19"
    class_a: str | None = None
    class_b: str | None = None
    qualifier: Literal["largest", "smallest"] | None = None
    comparator: Literal["ge", "le", "gt", "lt", "eq", "between"] | None = None
    stated_value: StatedValue | None = None
    stated_upper: StatedValue | None = None
    options: dict[str, str] = Field(default_factory=dict)
    point: tuple[float, float] | None = None
    negated: bool = False
    matched_rule: str = ""


class ParseFailure(BaseModel):
    """The parser declined. Recorded with a reason, never guessed around."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: str
    question: str


# --------------------------------------------------------------------------------------------
# Measured vocabulary. Every pattern below traces to a section of ANSWER_GRAMMAR.md.
# --------------------------------------------------------------------------------------------

#: §4 — MCQ options are enumerated `a) ... , b) ... , c) ... , d) ...`.
OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
#: §4 — referring-expression target wrapped in <ref> tags; referring point given as <point>.
REF_TAG = re.compile(r"<ref>(.*?)</ref>", re.I | re.S)
POINT_TAG = re.compile(r"<point>\s*\(\s*([\d.]+)[\s,]+([\d.]+)\s*\)\s*</point>", re.I)

#: §8 — the nine measured adjacency synonyms, plus the MCQ-stem paraphrases of the same
#: relation ("share a boundary/border/edge"), which the S9 residue surfaced.
ADJACENCY = re.compile(
    r"\btouch\w*\b|\badjacen\w*\b|\bborder\w*\b|\bnext to\b|\bcontact\b|\bmeet\w*\b"
    r"|\bneighbou?r\w*\b|\babut\w*\b|\bside by side\b"
    # "share a COMMON boundary" — an adjective may sit between the verb and the noun.
    r"|\bshares? (?:a |an )?(?:\w+ )?(?:boundary|border|edge|frontier)\b"
    # Paraphrases of the same relation, surfaced by the S9 residue rather than invented:
    # "lie right up against", "directly connected", "located alongside", "physically connect
    # to", "directly adjoin".
    r"|\bagainst\b|\balongside\b|\bconnects?\b|\bconnected (?:to|with)\b|\bdirectly connected\b"
    r"|\badjoin\w*\b|\bin (?:direct )?proximity\b|\bbutting\b",
    re.I,
)
#: §10 note — directional language appears in relative-position questions, not <ref> tags.
RELATIVE = re.compile(
    r"\brelative (?:position|location)\b|\bspatial (?:relation\w*|direction)\b"
    r"|\bpositioned (?:relative|with respect)\b|\bin relation to\b|\bsituated in relation\b"
    r"|\bdirectional relationship\b|\bspatially relate\b|\brelatively positioned\b"
    r"|\bwhere (?:is|are|does|do) the .+ (?:located|appear|lie)\b|\bas (?:the|a) reference\b"
    r"|\bcompare[sd]? spatially\b|\bdescribes? where\b|\bwhich direction\b"
    r"|\blocated compared\b|\bwhere the .+ (?:is|are) located\b",
    re.I,
)
#: §10 — exactly two operators, eight surface phrasings.
QUALIFIER = re.compile(
    r"\b(largest|smallest)\s+(?:patch|continuous area|contiguous area|connected region"
    r"|continuous region|connected patch|contiguous region|continuous patch)\b",
    re.I,
)
BARE_QUALIFIER = re.compile(r"\b(largest|smallest)\b", re.I)

#: §5 — counts as digits or number words.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
COUNT_CUE = re.compile(
    r"\bhow many\b|\bnumber of\b|\bcounts?\b|\bpatch(?:es)?\b|\bsegments?\b"
    r"|\bdistinct\b|\bseparate\b|\bclusters?\b|\binstances\b|\bparcels\b|\bblobs?\b",
    re.I,
)
#: A count is very often phrased as "N continuous regions of X" rather than with a count noun
#: alone. Measured: without this, "only a single continuous region of pastures" reads as
#: PRESENCE and "two or less continuous areas" reads as AREA, because `area` and `region` are
#: also area vocabulary. The shape — connectivity adjective + region noun — is what disambiguates.
COUNT_SHAPE = re.compile(
    r"\b(?:continuous|contiguous|connected|distinct|separate|individual|single)\s+"
    r"(?:areas?|regions?|patch(?:es)?|zones?|sections?|parts?|instances?|bodies|blobs?)\b",
    re.I,
)
#: §5 — area in two interchangeable units.
PCT = re.compile(r"([\d.]+)\s*(?:%|percent|per cent)", re.I)
#: All four spellings occur in real questions. MEASURED over 600 sampled items: `m2` 127,
#: `m^2` 109, `sq m`/`sqm` 97. Omitting `m^2` does not merely misroute — it drops the stated
#: value while still routing to AREA, which is a wrong number rather than an abstention.
M2_UNIT = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:m\^2|m2|m²|sq\.?\s?m(?:etres|eters)?\b|square\s+m(?:etres|eters)?\b)",
    re.I,
)
#: "land cover" / "land cover type" / "land cover class" is DOMAIN vocabulary, not an area cue.
#: It appears in most mcq|presence stems ("identify the land cover type in the image"), where
#: matching `cover\w*` sent the whole task to AREA.
LAND_COVER = re.compile(r"\bland[- ]cover\b|\bland cover\b|\bland[- ]use\b", re.I)
AREA_CUE = re.compile(
    r"\barea\b|\bcover\w*\b|\bextent\b|\boccup\w*\b|\bproportion\b|\bfraction\b|\bshare\b"
    r"|\btakes? up\b|\btake up\b|\baccounts? for\b|\bfilled\b|\bfills?\b|\bhow much\b"
    r"|\bmakes? up\b|\bspans?\b",
    re.I,
)
PRESENCE_CUE = re.compile(
    r"\bis there\b|\bare there\b|\bcontains?\b|\bcontaining\b|\bpresent\b|\bvisible\b"
    r"|\bappears?\b|\bany\b|\bidentify\b|\bcapture[sd]?\b|\binclude[sd]?\b|\bshows?\b"
    r"|\bfeature[sd]?\b|\bdetect\w*\b|\bobserve\w*\b|\bspot\b|\bfind\b|\bexist\w*\b"
    r"|\bdepict\w*\b|\bwhich class(?:es)?\b|\bcan you see\b|\bclassify\b|\bcorrespond\w*\b",
    re.I,
)
#: Captions are never MCQ, so this may be broad without competing with the closed tasks.
CAPTION_CUE = re.compile(
    r"\bdescribe\b|\bdescription\b|\bcaption\b|\bsummaris[ez]e\b|\bsummary\b|\boverview\b"
    r"|\bwhat do you see\b|\bnarrate\b|\bdetail the\b|\bexplain\b|\bwrite a\b"
    r"|\bgive an? (?:detailed )?(?:account|overview|description)\b|\bmentioning\b"
    r"|\bobserved features\b|\bimage content\b",
    re.I,
)
#: §3 — the three metadata MCQ categories. CLAUDE.md §7: these are ANSWER LABELS, never inputs.
#: PLURALS MATTER: "Which of the following season**s** / countr**ies** / climate zone**s**" is a
#: common stem, and singular-only patterns silently dropped 125 of 900 metadata MCQs.
METADATA_CUE = re.compile(
    r"\bcountr(?:y|ies)\b|\bnations?\b|\bwhich state\b|\bseasons?\b|\btime of year\b"
    r"|\bclimate (?:zones?|classifications?)\b|\bköppen\b|\bkoppen\b",
    re.I,
)

COMPARATORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ge", re.compile(r"\bat least\b|\bno (?:fewer|less) than\b|\bor more\b|\bminimum of\b", re.I)),
    ("le", re.compile(r"\bat most\b|\bno more than\b|\bor fewer\b|\bor less\b|\bup to\b", re.I)),
    ("gt", re.compile(r"\bmore than\b|\bgreater than\b|\bexceed\w*\b|\bover\b|\babove\b", re.I)),
    ("lt", re.compile(r"\bless than\b|\bfewer than\b|\bunder\b|\bbelow\b", re.I)),
    ("eq", re.compile(r"\bexactly\b|\bprecisely\b", re.I)),
)
#: A unit may sit between the two bounds: "between 864000 m^2 and 1152000 m^2". It must be
#: enumerated rather than skipped over generically, because `m^2` CONTAINS A DIGIT and any
#: "run of non-digits" shortcut stops dead on the 2.
_UNIT = (r"(?:%|percent|per cent|m\^2|m2|m²|sq\.?\s?m(?:etres|eters)?"
         r"|square\s+m(?:etres|eters)?)")
BETWEEN = re.compile(
    rf"\bbetween\b\s*([\d,]+(?:\.\d+)?)\s*{_UNIT}?\s*(?:and|to)\s*([\d,]+(?:\.\d+)?)",
    re.I,
)
#: S3 §7 — the complement phrasing. "Is there some part NOT covered by X" == coverage(X) < 100.
COMPLEMENT = re.compile(
    r"\bother (?:classes|types|land cover)\b|\bbesides\b|\bnot covered by\b|\bother than\b"
    r"|\bapart from\b|\baside from\b|\banything but\b|\bnot part of\b",
    re.I,
)
NEGATION = re.compile(
    r"\bnot covered by\b|\bother than\b|\bbesides\b|\bexcept\b|\bnot part of\b"
    r"|\bare not\b|\banything but\b|\bno\b(?= \w+ (?:present|visible))",
    re.I,
)


#: Where the option list starts. Splitting on "?" is NOT sufficient: many MCQ stems end with a
#: colon instead ("Select the class present in the image from the following: a) ..."), which
#: left the whole option list inside the stem and sent 68 presence MCQs to AREA because an
#: option named "Agro-forestry areas".
FIRST_OPTION = re.compile(r"(?:^|[?:.,;]\s*|\s)a\)\s")


def _split_stem_options(question: str) -> tuple[str, str]:
    """Split a question into ``(stem, options_segment)``.

    The option boundary is found by locating the first ``a)`` marker, falling back to the first
    question mark. Intent cues must be read from the stem alone: an option such as "to the left"
    would otherwise make every relative-position MCQ look like something else, and an option
    naming a class would produce a phantom ``class_b``.
    """
    m = FIRST_OPTION.search(question)
    if m:
        return question[:m.start()], question[m.start():]
    if "?" in question:
        head, tail = question.split("?", 1)
        return head, tail
    return question, ""


def _parse_options(question: str) -> dict[str, str]:
    _, seg = _split_stem_options(question)
    return {ll: t.strip().rstrip(".") for ll, t in OPTLET.findall(seg)}


@lru_cache(maxsize=4096)
def _form_pattern(form: str) -> re.Pattern[str]:
    """A whole-word, punctuation-tolerant matcher for one surface form.

    Two properties, both forced by measured data:

    - **Whole words only.** 14 surface forms are short enough to occur inside unrelated words:
      `sea` sits inside *season* and *research*, `urban` inside *suburban*, `town` inside
      *downtown*. Plain substring matching rewrote every ``mcq|season`` stem and drove that
      task's precision to **0.00%**.
    - **Commas are punctuation, not identity.** The table stores the class comma-stripped
      ("...agriculture with significant areas...") while real questions write it both with and
      without the comma. Letting each inter-word gap match ``[,\\s]+`` accepts either, and it
      matches against the *original* string so every offset stays exact for masking.
    """
    gap = r"[,\s]+"
    body = gap.join(re.escape(w) for w in form.split())
    return re.compile(rf"(?<![\w]){body}(?![\w])", re.I)


def _find_class_spans(text: str, syn: SynonymTable) -> list[tuple[int, int, str]]:
    """Class mentions as ``(start, end, canonical)``, longest surface form first.

    Two distinct correctness rules, both measured rather than assumed:

    1. **Longest form first, masking what it consumed.** Stops "inland waters" also matching
       "waters" and inventing a second class — the pattern that produced phantom `class_b`
       values at S8.
    2. **Whole-word matching only.** 14 surface forms in the table are short enough to occur
       inside unrelated words: `sea` sits inside *season* and *research*, `urban` inside
       *suburban*, `town` inside *downtown*, and `city`, `lake`, `river`, `field`, `tank`,
       `ocean` are all similarly exposed. Substring matching silently rewrote every
       ``mcq|season`` stem to " _CLASS_ son" and drove that task's precision to **0.00%**.
       It would also have mis-resolved `class_a` anywhere those words appear.
    """
    low = text.lower()
    consumed = [False] * len(low)
    found: list[tuple[int, int, str]] = []
    for form in sorted(syn.forms, key=len, reverse=True):
        for m in _form_pattern(form).finditer(low):
            start, end = m.start(), m.end()
            if not any(consumed[start:end]):
                for i in range(start, end):
                    consumed[i] = True
                found.append((start, end, syn.resolve(form).canonical))
                break
    return sorted(found)


def _find_classes(text: str, syn: SynonymTable) -> list[str]:
    """Canonical classes mentioned, in order of appearance, de-duplicated."""
    ordered: list[str] = []
    for _, _, name in _find_class_spans(text, syn):
        if name not in ordered:
            ordered.append(name)
    return ordered


def _cue_text(stem: str, syn: SynonymTable) -> str:
    """The stem with every class mention blanked out, for intent-cue matching only.

    **A class name is not an intent cue.** Measured: matching cues against the raw stem sent
    151 presence questions to AREA, because the class
    *"Land principally occupied by agriculture, with significant areas of natural vegetation"*
    contains both "occupied" and "areas" and fires two area cues on its own. `Coastal wetlands`,
    `agro-forestry areas` and `transitional woodland, shrub` have the same problem to a lesser
    degree.

    This is the same lesson as reading intent from the stem rather than the options, applied one
    level deeper: the question's *wording about the task* is what carries the intent, and the
    class name is payload, not wording.
    """
    spans = _find_class_spans(stem, syn)
    if not spans:
        return stem
    out, prev = [], 0
    for s, e, _ in spans:
        out.append(stem[prev:s])
        out.append(" _CLASS_ ")
        prev = e
    out.append(stem[prev:])
    return "".join(out)


def _stated_area(text: str) -> StatedValue | None:
    """An area stated in either measured unit, normalised to percent of patch."""
    m = PCT.search(text)
    if m:
        v = float(m.group(1))
        return StatedValue(raw=m.group(0), unit="percent", value=v, as_percent=v)
    m = M2_UNIT.search(text)
    if m:
        v = float(m.group(1).replace(",", ""))
        return StatedValue(raw=m.group(0), unit="m2", value=v,
                           as_percent=100.0 * v / PATCH_AREA_M2)
    return None


def _stated_count(text: str) -> StatedValue | None:
    """A count stated as a number word or digits. Words are checked first (S3: they dominate)."""
    low = text.lower()
    for word, val in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            return StatedValue(raw=word, unit="count", value=float(val))
    m = re.search(r"\b(\d+)\b", text)
    if m:
        return StatedValue(raw=m.group(1), unit="count", value=float(m.group(1)))
    return None


def _comparator(text: str) -> str | None:
    return next((n for n, rx in COMPARATORS if rx.search(text)), None)


def _qualifier(text: str) -> Literal["largest", "smallest"] | None:
    m = QUALIFIER.search(text) or BARE_QUALIFIER.search(text)
    if m is None:
        return None
    return "largest" if m.group(1).lower() == "largest" else "smallest"


def _classify(cue: str, is_mcq: bool) -> tuple[Intent, str] | None:
    """Intent from CLASS-MASKED stem cues. Order is load-bearing, documented per branch.

    ``cue`` must come from :func:`_cue_text`, not from the raw stem.
    """
    # Metadata first: "which country" is not a land-cover question at all, and CLAUDE.md §7
    # makes misrouting one actively dangerous rather than merely wrong.
    # GATED ON is_mcq: all three metadata categories are MCQ-only (S3 §1), and captions say
    # "including the region, time of year, and land cover classes" — which sent 71 captions
    # to METADATA_MCQ until this gate was added.
    if is_mcq and METADATA_CUE.search(cue):
        return Intent.METADATA_MCQ, "metadata_cue"
    # Relative position before adjacency: "in relation to" co-occurs with positional wording,
    # and several relative-position stems mention neither a compass term nor a qualifier.
    if RELATIVE.search(cue):
        return Intent.RELATIVE_POSITION, "relative_cue"
    # Adjacency before count/area: "Is any X and Y side by side" also contains a presence cue.
    if ADJACENCY.search(cue):
        return Intent.ADJACENCY, "adjacency_synonym"
    # An explicit unit beats everything: "covers more than 30%" is an area question however it
    # is otherwise worded. Units are the strongest available signal, so they are tested first.
    if PCT.search(cue) or M2_UNIT.search(cue):
        return Intent.AREA, "area_quantity"
    # Then the count SHAPE ("a single continuous region of ...") before generic area nouns,
    # because `area` and `region` belong to both vocabularies and only the shape separates them.
    if COUNT_SHAPE.search(cue):
        return Intent.COUNT, "count_shape"
    if COUNT_CUE.search(cue):
        return Intent.COUNT, "count_cue"
    # The COMPLEMENT form — "does the image show other classes besides X" — asks whether
    # coverage(X) < 100%. S3 §7 classifies it as an area question, and the released labels
    # agree; read literally it looks like a presence question, which is where it used to go.
    if COMPLEMENT.search(cue):
        return Intent.AREA, "complement_form"
    # "land cover type" is domain vocabulary, not an area cue — strip it before asking.
    if AREA_CUE.search(LAND_COVER.sub(" ", cue)):
        return Intent.AREA, "area_cue"
    if PRESENCE_CUE.search(cue):
        return Intent.PRESENCE, "presence_cue"
    if is_mcq:
        return Intent.PRESENCE, "mcq_default_presence"
    return None


def parse_query(question: str, syn: SynonymTable, *, level: Level = "c19"
                ) -> QuerySpec | ParseFailure:
    """Parse one question into a :class:`QuerySpec`.

    Args:
        question: Raw question text, exactly as the benchmark states it.
        syn: Loaded synonym table, for class resolution.
        level: CLC level the question is posed at. S3: always the 19-class vocabulary.

    Returns:
        A :class:`QuerySpec`, or a :class:`ParseFailure` naming why the rules declined.
    """
    if not isinstance(question, str) or not question.strip():
        return ParseFailure(reason="empty question", question=str(question)[:200])
    if len(question) > 4000:
        return ParseFailure(reason="question exceeds 4000 chars", question=question[:200])

    # --- tagged input forms are unambiguous and are checked before any keyword cue ----------
    pt = POINT_TAG.search(question)
    if pt:
        return QuerySpec(
            intent=Intent.REFERRING_POINT, answer_format=AnswerFormat.BBOX, clc_level=level,
            point=(float(pt.group(1)), float(pt.group(2))),
            class_a=next(iter(_find_classes(question, syn)), None),
            qualifier=_qualifier(question), matched_rule="point_tag",
        )
    ref = REF_TAG.search(question)
    if ref:
        inner = ref.group(1)
        classes = _find_classes(inner, syn) or _find_classes(question, syn)
        if not classes:
            return ParseFailure(reason="<ref> tag resolved to no class", question=question[:200])
        return QuerySpec(
            intent=Intent.REFERRING_EXPR, answer_format=AnswerFormat.BBOX, clc_level=level,
            class_a=classes[0], qualifier=_qualifier(inner), matched_rule="ref_tag",
        )

    stem, _ = _split_stem_options(question)
    options = _parse_options(question)
    is_mcq = len(options) == 4

    # Intent cues are read from the stem with class mentions blanked out. See _cue_text.
    cue = _cue_text(stem, syn)

    if CAPTION_CUE.search(cue) and not is_mcq:
        return QuerySpec(intent=Intent.CAPTION, answer_format=AnswerFormat.FREE_TEXT,
                         clc_level=level, matched_rule="caption_cue")

    hit = _classify(cue, is_mcq)
    if hit is None:
        return ParseFailure(reason="no intent cue matched", question=question[:200])
    intent, rule = hit

    fmt = AnswerFormat.MCQ_LETTER if is_mcq else AnswerFormat.YES_NO
    if intent is Intent.METADATA_MCQ:
        # Metadata answers are the label CLAUDE.md §7 forbids as an input. No class is
        # resolved and none is carried, so nothing downstream can read one by accident.
        return QuerySpec(intent=intent, answer_format=fmt, clc_level=level,
                         options=options, matched_rule=rule)

    classes = _find_classes(stem, syn)
    need_two = intent in (Intent.ADJACENCY, Intent.RELATIVE_POSITION)

    if is_mcq and len(classes) < (2 if need_two else 1):
        # An MCQ often names no class in the stem at all — "Which class appears in the image?",
        # "Which classes share a boundary?" — because the candidates ARE the options. Looking
        # there is not a guess: the options are printed in the question and available at
        # inference. S8 measured this as 20.3% abstention on mcq|adjacency alone.
        for text in options.values():
            found = _find_classes(text, syn)
            if len(found) >= (2 if need_two else 1):
                return QuerySpec(
                    intent=intent, answer_format=fmt, clc_level=level,
                    class_a=found[0], class_b=found[1] if need_two else None,
                    options=options, qualifier=_qualifier(cue),
                    matched_rule=f"{rule}+option_classes",
                )

    if not classes:
        return ParseFailure(reason="no class name resolved in the stem", question=question[:200])
    if need_two and len(classes) < 2:
        return ParseFailure(reason=f"{intent.value} needs two classes, found {len(classes)}",
                            question=question[:200])

    spec: dict[str, Any] = {
        "intent": intent, "answer_format": fmt, "clc_level": level,
        "class_a": classes[0], "class_b": classes[1] if len(classes) > 1 else None,
        "options": options, "qualifier": _qualifier(cue),
        "negated": bool(NEGATION.search(cue)), "matched_rule": rule,
    }

    # Quantities are also read from the class-masked text, so a class name can never contribute
    # a stray number or comparator to the extracted value.
    if not is_mcq:
        rng = BETWEEN.search(cue)
        if rng and intent in (Intent.AREA, Intent.COUNT):
            lo, hi = (float(rng.group(i).replace(",", "")) for i in (1, 2))
            is_area = intent is Intent.AREA
            is_m2 = bool(M2_UNIT.search(cue)) and is_area
            unit: Literal["percent", "m2", "count"] = (
                "m2" if is_m2 else ("percent" if is_area else "count"))

            def _bound(v: float, *, _u: Literal["percent", "m2", "count"] = unit,
                       _m2: bool = is_m2, _area: bool = is_area) -> StatedValue:
                assert rng is not None
                return StatedValue(
                    raw=rng.group(0), unit=_u, value=v,
                    as_percent=(100.0 * v / PATCH_AREA_M2) if _m2
                    else (v if _area else None))

            spec["comparator"] = "between"
            spec["stated_value"] = _bound(lo)
            spec["stated_upper"] = _bound(hi)
        elif intent is Intent.AREA:
            spec["comparator"] = _comparator(cue)
            spec["stated_value"] = _stated_area(cue)
        elif intent is Intent.COUNT:
            spec["comparator"] = _comparator(cue)
            spec["stated_value"] = _stated_count(cue)

    return QuerySpec(**spec)
