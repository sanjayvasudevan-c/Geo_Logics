"""Oracle answer producer — M2 driven by GROUND-TRUTH maps (S8 / GATE 1).

This measures ``ORACLE(t)`` in ``TARGET(t) = ORACLE(t) × TRANSFER(t)``: the accuracy the
symbolic path would reach **if segmentation were perfect**. It needs no GPU and no trained
model, which is exactly why the architecture puts it before M1 training — if the oracle is low,
the answer grammar is wrong and no amount of segmentation quality can rescue it.

The question parser here is deliberately narrow: it handles the closed template forms S3
measured, and **abstains rather than guessing** on anything else. An abstention is scored as a
parse failure and reported separately, so a low oracle can be attributed to the right cause —
parser, convention, or genuine geometric limit — rather than blamed on the method as a whole.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from satquery.config.schema import M2Config
from satquery.exceptions import GeometryError, TaxonomyError
from satquery.geometry import (
    GeometryParams,
    compute_adjacency,
    compute_relative_position,
    extract_regions,
)
from satquery.taxonomy import SynonymTable, Taxonomy

__all__ = ["OracleAnswer", "ParseFailure", "answer_question", "parse_question"]

IntArray = npt.NDArray[np.integer[Any]]

OPTLET = re.compile(r"(?:^|[,;]\s*|\s)([a-d])\)\s*(.+?)(?=(?:[,;]\s*|\s)[a-d]\)|$)")
RANGE = re.compile(r"([\d,\.]+)\s*to\s*([\d,\.]+)")
BETWEEN = re.compile(r"between\s+([\d,\.]+)\s*(?:%|square meters|sqm|m2|m²)?\s*and\s+([\d,\.]+)",
                     re.I)
PCT = re.compile(r"([\d]+(?:\.\d+)?)\s*%")
M2_UNIT = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:m2|m\^2|m²|sqm|square met(?:er|re)s?)", re.I)
INT_ONLY = re.compile(r"^\s*([\d,]+)\s*$")
PATCH_AREA_M2 = 1_440_000.0

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a single": 1,
}

#: Comparators, most specific first so "at least" is not swallowed by a looser pattern.
COMPARATORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ge", re.compile(r"\bat least\b|\bno less than\b|\bor more\b|\bminimum of\b", re.I)),
    ("le", re.compile(r"\bat most\b|\bno more than\b|\bor fewer\b|\bor less\b", re.I)),
    ("gt", re.compile(r"\bmore than\b|\bgreater than\b|\bexceed\w*\b|\bover\b|\babove\b", re.I)),
    ("lt", re.compile(r"\bless than\b|\bfewer than\b|\bunder\b|\bbelow\b", re.I)),
    ("eq", re.compile(r"\bexactly\b|\bprecisely\b", re.I)),
)

#: Complement forms: "is there some part NOT covered by X" == coverage(X) < 100.
COMPLEMENT = re.compile(
    r"not covered by|other than|besides|except|not part of|are not|anything but", re.I
)
#: Singularity / plurality, measured at S3 as the bulk of the residual count forms.
ONLY_ONE = re.compile(r"only (?:a single|one)\b", re.I)
MULTIPLE = re.compile(r"\bmultiple\b|\bmore than one\b|\bseveral\b", re.I)

#: Option text -> compass. COMPOUND FORMS FIRST: "bottom-left" must be consumed as SW before
#: "bottom" can match it as S. Matching a single letter as a substring of the computed direction
#: was a real bug — for a computed "SE", the option "bottom-left" matched because "S" in "SE".
DIRECTION_PHRASES: tuple[tuple[str, str], ...] = (
    ("top-left", "NW"), ("top left", "NW"), ("upper-left", "NW"), ("north-west", "NW"),
    ("top-right", "NE"), ("top right", "NE"), ("upper-right", "NE"), ("north-east", "NE"),
    ("bottom-left", "SW"), ("bottom left", "SW"), ("lower-left", "SW"), ("south-west", "SW"),
    ("bottom-right", "SE"), ("bottom right", "SE"), ("lower-right", "SE"), ("south-east", "SE"),
    ("top", "N"), ("above", "N"), ("north", "N"), ("upper", "N"),
    ("bottom", "S"), ("below", "S"), ("south", "S"), ("lower", "S"),
    ("left", "W"), ("west", "W"),
    ("right", "E"), ("east", "E"),
)

#: Compass bearing in degrees, for angular nearest-option fallback.
BEARING = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}


def option_direction(text: str) -> str | None:
    """Compass for an MCQ option, longest phrase first so compounds win."""
    low = text.lower()
    for phrase, compass in DIRECTION_PHRASES:
        if phrase in low:
            return compass
    return None


def angular_gap(a: str, b: str) -> float:
    """Smallest angle between two compass directions, in degrees."""
    d = abs(BEARING[a] - BEARING[b]) % 360
    return min(d, 360 - d)


@dataclass(frozen=True)
class ParseFailure:
    """The parser abstained. Recorded, never guessed around."""

    reason: str
    question: str


@dataclass(frozen=True)
class OracleAnswer:
    """A produced answer plus everything needed to audit it."""

    answer: str
    task: str
    computed: float | None = None
    detail: dict[str, Any] | None = None


def _find_classes(question: str, syn: SynonymTable) -> list[str]:
    """Canonical classes mentioned, longest surface form first so substrings do not win."""
    low = question.lower()
    consumed = [False] * len(low)
    found: list[tuple[int, str]] = []
    # Longest form first, and mask what it consumed, so "inland waters" cannot also match
    # "waters" and produce a phantom second class.
    for form in sorted(syn.forms, key=len, reverse=True):
        start = low.find(form)
        while start >= 0:
            end = start + len(form)
            if not any(consumed[start:end]):
                for i in range(start, end):
                    consumed[i] = True
                found.append((start, syn.resolve(form).canonical))
                break
            start = low.find(form, start + 1)
    ordered: list[str] = []
    for _, name in sorted(found):
        if name not in ordered:
            ordered.append(name)
    return ordered


def _number_in(question: str) -> float | None:
    """Threshold from a count question, digits or number words."""
    low = question.lower()
    for word, val in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            return float(val)
    m = re.search(r"\b(\d+)\b", question)
    return float(m.group(1)) if m else None


def _coverage_threshold(question: str) -> float | None:
    """Area threshold as a percentage, whichever unit the question used."""
    m = PCT.search(question)
    if m:
        return float(m.group(1))
    m = M2_UNIT.search(question)
    if m:
        return 100.0 * float(m.group(1).replace(",", "")) / PATCH_AREA_M2
    return None


def parse_question(
    question: str, task: str, syn: SynonymTable
) -> dict[str, Any] | ParseFailure:
    """Parse one templated question into a typed intent.

    Abstains — returns :class:`ParseFailure` — rather than guessing. S7's fitting showed the
    parser is the component most likely to be silently wrong, so a miss must be visible.
    """
    classes = _find_classes(question, syn)
    kind, category = task.split("|", 1)

    if category in ("country", "season", "climate zone"):
        return ParseFailure("metadata task: not geometry-derived", question)

    if kind == "mcq":
        seg = question.split("?", 1)[-1] if "?" in question else question
        options = {ll: t.strip().rstrip(".") for ll, t in OPTLET.findall(seg)}
        if len(options) != 4:
            return ParseFailure(f"expected 4 options, parsed {len(options)}", question)
        return {"kind": "mcq", "category": category, "classes": classes, "options": options}

    if kind == "binary":
        comparator = next((n for n, rx in COMPARATORS if rx.search(question)), None)
        rng = BETWEEN.search(question)
        return {
            "kind": "binary", "category": category, "classes": classes,
            "comparator": comparator,
            "range": (float(rng.group(1).replace(",", "")), float(rng.group(2).replace(",", "")))
            if rng else None,
            "threshold_pct": _coverage_threshold(question),
            "threshold_n": _number_in(question),
            "complement": bool(COMPLEMENT.search(question)),
            "only_one": bool(ONLY_ONE.search(question)),
            "multiple": bool(MULTIPLE.search(question)),
            "is_m2_unit": bool(M2_UNIT.search(question)),
        }
    return ParseFailure(f"unsupported task kind: {kind}", question)


def _compare(value: float, comparator: str | None, threshold: float) -> bool | None:
    """Apply a comparator. Inclusive forms include the boundary (S3, confirmed at S7)."""
    if comparator == "ge":
        return value >= threshold
    if comparator == "le":
        return value <= threshold
    if comparator == "gt":
        return value > threshold
    if comparator == "lt":
        return value < threshold
    if comparator == "eq":
        return value == threshold
    return None


def answer_question(
    class_map: IntArray,
    question: str,
    task: str,
    taxonomy: Taxonomy,
    syn: SynonymTable,
    params: GeometryParams,
    cfg: M2Config,
    level: Literal["c19"] = "c19",
) -> OracleAnswer | ParseFailure:
    """Produce an answer from a ground-truth map. The oracle's answer producer.

    Args:
        class_map: Ground-truth CORINE code map.
        question: The templated question text.
        task: ``"<type>|<category>"``.
        taxonomy: Loaded taxonomy.
        syn: Loaded synonym table.
        params: Fitted geometry parameters.
        cfg: M2 config, for the referring filters.
        level: Level questions are posed at. S3: always the 19-class vocabulary.

    Returns:
        An :class:`OracleAnswer`, or :class:`ParseFailure` if the parser abstained.
    """
    parsed = parse_question(question, task, syn)
    if isinstance(parsed, ParseFailure):
        return parsed
    classes: list[str] = parsed["classes"]
    category = parsed["category"]

    try:
        if category == "adjacency":
            if len(classes) < 2:
                return ParseFailure("adjacency needs two classes", question)
            if parsed["kind"] == "binary":
                res = compute_adjacency(
                    class_map, classes[0], classes[1], level, taxonomy, params
                )
                return OracleAnswer("yes" if res.adjacent else "no", task,
                                    detail={"overlap_px": res.overlap_px})
            best, best_ok = None, -1
            for letter, text in parsed["options"].items():
                names = [
                    syn.resolve(f).canonical for f in sorted(syn.forms, key=len, reverse=True)
                    if f in text.lower()
                ]
                names = list(dict.fromkeys(names))
                if len(names) < 2:
                    continue
                adj = compute_adjacency(class_map, names[0], names[1], level, taxonomy, params)
                score = adj.overlap_px if adj.adjacent else -1
                if score > best_ok:
                    best, best_ok = letter, score
            return (OracleAnswer(best, task) if best
                    else ParseFailure("no MCQ option yielded two classes", question))

        if not classes:
            return ParseFailure("no class name resolved", question)
        target = classes[0]
        regions = extract_regions(class_map, target, level, taxonomy, params)
        count = len(regions)
        coverage_pct = 100.0 * regions.coverage

        if category == "presence":
            if parsed["kind"] == "binary":
                return OracleAnswer("yes" if count > 0 else "no", task, computed=float(count))
            best_letter, best_cov = None, -1.0
            for letter, text in parsed["options"].items():
                names = [
                    syn.resolve(f).canonical for f in sorted(syn.forms, key=len, reverse=True)
                    if f in text.lower()
                ]
                if not names:
                    continue
                candidate = extract_regions(class_map, names[0], level, taxonomy, params)
                if candidate.coverage > best_cov:
                    best_letter, best_cov = letter, candidate.coverage
            return (OracleAnswer(best_letter, task, computed=best_cov) if best_letter
                    else ParseFailure("no MCQ option resolved to a class", question))

        if category == "count":
            if parsed["kind"] == "mcq":
                best_letter, best_gap = None, float("inf")
                for letter, text in parsed["options"].items():
                    m = INT_ONLY.match(text)  # noqa: SIM102
                    if not m:
                        continue
                    gap = float(abs(count - int(m.group(1).replace(",", ""))))
                    if gap < best_gap:
                        best_letter, best_gap = letter, gap
                return (OracleAnswer(best_letter, task, computed=float(count)) if best_letter
                        else ParseFailure("no numeric MCQ option", question))
            if parsed["only_one"]:
                return OracleAnswer("yes" if count == 1 else "no", task, computed=float(count))
            if parsed["multiple"]:
                return OracleAnswer("yes" if count >= 2 else "no", task, computed=float(count))
            n = parsed["threshold_n"]
            if n is None:
                return ParseFailure("count question with no threshold", question)
            verdict = _compare(float(count), parsed["comparator"], n)
            if verdict is None:
                return ParseFailure("count question with no comparator", question)
            return OracleAnswer("yes" if verdict else "no", task, computed=float(count))

        if category == "area":
            if parsed["kind"] == "mcq":
                best_letter = None
                for letter, text in parsed["options"].items():
                    m = RANGE.search(text)
                    if not m:
                        continue
                    lo = float(m.group(1).replace(",", ""))
                    hi = float(m.group(2).replace(",", ""))
                    if "%" not in text:
                        lo = 100.0 * lo / PATCH_AREA_M2
                        hi = 100.0 * hi / PATCH_AREA_M2
                    if lo <= coverage_pct <= hi:
                        best_letter = letter
                        break
                if best_letter is None:   # gapped options: fall back to nearest range
                    best_gap = float("inf")
                    for letter, text in parsed["options"].items():
                        m = RANGE.search(text)
                        if not m:
                            continue
                        lo = float(m.group(1).replace(",", ""))
                        hi = float(m.group(2).replace(",", ""))
                        if "%" not in text:
                            lo, hi = 100.0 * lo / PATCH_AREA_M2, 100.0 * hi / PATCH_AREA_M2
                        gap = 0.0 if lo <= coverage_pct <= hi else min(
                            abs(coverage_pct - lo), abs(coverage_pct - hi))
                        if gap < best_gap:
                            best_letter, best_gap = letter, gap
                return (OracleAnswer(best_letter, task, computed=coverage_pct) if best_letter
                        else ParseFailure("no range MCQ option", question))
            if parsed["complement"]:
                return OracleAnswer("yes" if coverage_pct < 100.0 else "no", task,
                                    computed=coverage_pct)
            if parsed["range"] is not None:
                lo, hi = parsed["range"]
                if parsed["is_m2_unit"]:
                    lo, hi = 100.0 * lo / PATCH_AREA_M2, 100.0 * hi / PATCH_AREA_M2
                return OracleAnswer("yes" if lo <= coverage_pct <= hi else "no", task,
                                    computed=coverage_pct)
            th = parsed["threshold_pct"]
            if th is None:
                return ParseFailure("area question with no threshold", question)
            verdict = _compare(coverage_pct, parsed["comparator"], th)
            if verdict is None:
                return ParseFailure("area question with no comparator", question)
            return OracleAnswer("yes" if verdict else "no", task, computed=coverage_pct)

        if category == "relative pos":
            if len(classes) < 2:
                return ParseFailure("relative position needs two classes", question)
            a = extract_regions(class_map, classes[0], level, taxonomy, params)
            b = extract_regions(class_map, classes[1], level, taxonomy, params)
            rel = compute_relative_position(a, b)
            if not rel.valid:
                return ParseFailure("one class absent; direction undefined", question)
            # EXACT compound match first.
            opts = {ll: option_direction(t) for ll, t in parsed["options"].items()}
            for letter, compass in opts.items():
                if compass == rel.direction:
                    return OracleAnswer(letter, task, detail={"direction": rel.direction,
                                                              "match": "exact"})
            # Otherwise the angularly NEAREST offered option. Ties are reported, not hidden:
            # e.g. a computed SW is equidistant from an offered S and W.
            usable = {ll: c for ll, c in opts.items() if c is not None}
            if not usable:
                return ParseFailure("no option parsed as a direction", question)
            gaps = {ll: angular_gap(rel.direction, c) for ll, c in usable.items()}
            best = min(gaps.values())
            tied = [ll for ll, g in gaps.items() if g == best]
            return OracleAnswer(
                sorted(tied)[0], task,
                detail={"direction": rel.direction, "match": "nearest",
                        "gap_deg": best, "tied": len(tied)},
            )

    except (GeometryError, TaxonomyError) as exc:
        return ParseFailure(f"{type(exc).__name__}: {exc.message}", question)

    return ParseFailure(f"unhandled category: {category}", question)
