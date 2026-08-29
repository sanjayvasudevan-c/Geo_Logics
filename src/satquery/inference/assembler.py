"""Answer assembly — pipeline stage 9.

Named ``Assembler`` per the S0 gate decision (IMPLEMENTATION_MAP §10.2 A4): ``A1`` is reserved
exclusively for the Stage S16 falsification experiment and is never a component name.

This component is the enforcement point for the number-flow rule (CLAUDE.md §2): the numeric
value in an answer comes from M2 and is *substituted into* a template. A language model may
phrase an answer; it may never produce the number in it.

Not implemented as of Stage S1.
"""

from __future__ import annotations

from typing import Any

__all__ = ["AnswerAssembler"]


class AnswerAssembler:
    """Assembles the final answer, evidence references and execution trace.

    Every method raises :class:`NotImplementedError` until the stage that builds it. Stage S1
    is the foundation only, and a stub that returned a plausible-looking value would violate
    CLAUDE.md §5.
    """

    def assemble(
        self,
        *,
        computed_value: Any,
        unit: str | None,
        confidence: float,
        evidence_refs: list[str],
        trace: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble a structured answer.

        Args:
            computed_value: The value produced by M2. Never parsed out of generated text.
            unit: Unit of ``computed_value``, e.g. ``"m^2"``.
            confidence: Calibrated ``P(answer correct)`` from M9.
            evidence_refs: Identifiers of the evidence artifacts backing this answer.
            trace: The execution trace accumulated across the pipeline.

        Returns:
            The structured JSON response.

        Raises:
            NotImplementedError: Always, as of Stage S1.
        """
        raise NotImplementedError(
            "AnswerAssembler.assemble is not implemented as of Stage S1"
        )
