"""Every exception type is constructible and carries context."""

from __future__ import annotations

import pytest

from satquery.exceptions import (
    ConfigError,
    ContractViolationError,
    GeometryError,
    InputValidationError,
    ModelError,
    RoutingError,
    SatQueryError,
    TaxonomyError,
)

pytestmark = pytest.mark.unit

ALL_ERRORS = [
    ConfigError,
    ContractViolationError,
    GeometryError,
    InputValidationError,
    ModelError,
    RoutingError,
    TaxonomyError,
]


@pytest.mark.parametrize("error_type", ALL_ERRORS, ids=lambda t: t.__name__)
class TestEveryErrorType:
    def test_is_constructible_with_message_only(self, error_type: type[SatQueryError]) -> None:
        error = error_type("something went wrong")
        assert error.message == "something went wrong"
        assert error.context == {}

    def test_carries_structured_context(self, error_type: type[SatQueryError]) -> None:
        error = error_type("failed", component="M2", value=7, path="configs/m2.yaml")
        assert error.context == {"component": "M2", "value": 7, "path": "configs/m2.yaml"}

    def test_derives_from_base(self, error_type: type[SatQueryError]) -> None:
        assert issubclass(error_type, SatQueryError)
        assert issubclass(error_type, Exception)

    def test_is_raisable_and_catchable_as_base(self, error_type: type[SatQueryError]) -> None:
        with pytest.raises(SatQueryError) as info:
            raise error_type("boom", stage="S1")
        assert isinstance(info.value, error_type)
        assert info.value.context["stage"] == "S1"

    def test_str_includes_message_and_context(self, error_type: type[SatQueryError]) -> None:
        rendered = str(error_type("bad thing", field="connectivity"))
        assert "bad thing" in rendered
        assert "connectivity" in rendered

    def test_repr_is_informative(self, error_type: type[SatQueryError]) -> None:
        rendered = repr(error_type("bad thing", field="x"))
        assert error_type.__name__ in rendered
        assert "bad thing" in rendered

    def test_to_dict_is_trace_ready(self, error_type: type[SatQueryError]) -> None:
        record = error_type("failed", component="M1").to_dict()
        assert record["error_type"] == error_type.__name__
        assert record["message"] == "failed"
        assert record["context"] == {"component": "M1"}

    def test_context_is_a_copy_not_a_shared_reference(
        self, error_type: type[SatQueryError]
    ) -> None:
        error = error_type("failed", component="M1")
        error.to_dict()["context"]["component"] = "MUTATED"
        assert error.context["component"] == "M1"


class TestBaseError:
    def test_base_is_constructible(self) -> None:
        error = SatQueryError("generic failure", detail=1)
        assert error.message == "generic failure"
        assert error.context == {"detail": 1}

    def test_str_without_context_is_just_the_message(self) -> None:
        assert str(SatQueryError("plain")) == "plain"

    def test_hierarchy_is_flat_under_the_base(self) -> None:
        """No error type is a subclass of a sibling — catching one must not catch another."""
        for error_type in ALL_ERRORS:
            siblings = [s for s in ALL_ERRORS if s is not error_type]
            assert not any(issubclass(error_type, s) for s in siblings), (
                f"{error_type.__name__} shadows a sibling"
            )

    def test_distinct_types_are_separately_catchable(self) -> None:
        with pytest.raises(GeometryError):
            raise GeometryError("m2 failed")
        with pytest.raises(TaxonomyError):
            raise TaxonomyError("bad aggregation")


class TestContractViolation:
    def test_carries_the_violated_invariant(self) -> None:
        """CLAUDE.md §2 violations must be legible in the trace."""
        error = ContractViolationError(
            "number produced outside M2",
            rule="number_flow",
            producer="M7",
            expected_producer="M2",
        )
        assert error.context["rule"] == "number_flow"
        assert error.context["producer"] == "M7"
