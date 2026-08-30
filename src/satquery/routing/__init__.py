"""Q1 intent parsing and R1 deterministic routing. No LLM planner, no eval().

S9 builds Q1 (:mod:`satquery.routing.parser`) and its M10 fallback
(:mod:`satquery.routing.m10_classifier`). R1 itself arrives at S10.
"""

from __future__ import annotations

from satquery.routing.m10_classifier import (
    TASK_TO_INTENT,
    M10Classifier,
    TrainedM10,
    task_to_intent,
)
from satquery.routing.parser import (
    AnswerFormat,
    Intent,
    ParseFailure,
    QuerySpec,
    StatedValue,
    parse_query,
)

__all__ = [
    "TASK_TO_INTENT",
    "AnswerFormat",
    "Intent",
    "M10Classifier",
    "ParseFailure",
    "QuerySpec",
    "StatedValue",
    "TrainedM10",
    "parse_query",
    "task_to_intent",
]
