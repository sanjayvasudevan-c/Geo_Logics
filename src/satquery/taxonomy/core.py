"""CORINE hierarchy and the aggregation layer (M2 step 0).

This is the fix for the architecture's single most important correction: **44 CORINE Level-3
classes are the segmentation target; the 19-class scheme is not** (CLAUDE.md §1). S3 then
established that *questions* are asked exclusively in the 19-class vocabulary, so aggregation
from L3 to the queried level is on the critical path for every geometric answer.

**THE AGGREGATION-BEFORE-GEOMETRY GUARANTEE.** Hierarchy aggregation must happen *before*
connected-component analysis. A city split into continuous (111) and discontinuous (112) urban
fabric is **one** urban region, not two; running components on the raw L3 map would count two
and be systematically wrong. IMPLEMENTATION_MAP §5.3 ranks a wrong aggregation table as the
second most damaging silent failure in the system. :func:`mask_for` enforces the order by
construction — it aggregates and then returns a mask, so a caller cannot run components on an
un-aggregated map through this API.

Two coordinate systems exist and must not be confused:

- **code space** — the CORINE codes the reference maps actually store (111, 112, …, 523) plus
  ``999`` for unclassified. This is what lands on disk.
- **index space** — contiguous training indices 0–43 that M1's head emits.

Conversion is explicit (:meth:`Taxonomy.codes_to_indices` / :meth:`indices_to_codes`); nothing
here silently assumes one or the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import yaml

from satquery.exceptions import TaxonomyError
from satquery.utils.paths import project_root

#: Integer label array in some class-id space (CORINE codes, or a level's ids).
IntArray = npt.NDArray[np.integer[Any]]

__all__ = ["LEVELS", "Level", "Taxonomy", "load_taxonomy"]

NOMENCLATURE = "configs/taxonomy/corine_l3.yaml"

Level = Literal["l1", "l2", "l3", "c19", "coarse7"]
LEVELS: tuple[Level, ...] = ("l1", "l2", "l3", "c19", "coarse7")

#: Sentinel for pixels with no counterpart at the requested level. 11 of the 44 L3 classes have
#: no 19-class equivalent, so L3->19 is a PARTIAL function; those pixels land here rather than
#: being folded into a neighbouring class.
NO_EQUIVALENT = -1

#: Sentinel for unclassified (code 999) at every level. Never a valid class.
UNCLASSIFIED = -2

#: Multiplier for a confusion that crosses a CORINE Level-1 branch (CLAUDE.md §1: `L_hier`).
CROSS_L1_PENALTY = 1.5
#: Multiplier for a confusion within a Level-3 sibling group.
SIBLING_PENALTY = 1.0


@dataclass(frozen=True)
class ClassEntry:
    """One CORINE Level-3 class."""

    code: int
    index: int
    name: str
    l2: int
    l1: int
    to_19: str | None
    to_coarse7: str
    provenance: str


class Taxonomy:
    """The loaded CORINE hierarchy with typed aggregation operations."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.classes: tuple[ClassEntry, ...] = tuple(
            ClassEntry(
                code=int(e["code"]), index=int(e["index"]), name=str(e["name"]),
                l2=int(e["l2"]), l1=int(e["l1"]), to_19=e["to_19"],
                to_coarse7=str(e["to_coarse7"]), provenance=str(e["provenance"]),
            )
            for e in raw["classes"]
        )
        self.unclassified_code: int = int(raw["unclassified"]["code"])
        self.level_1: dict[int, str] = {int(k): str(v) for k, v in raw["level_1"].items()}
        self.level_2: dict[int, str] = {int(k): str(v) for k, v in raw["level_2"].items()}
        self.coarse_7: tuple[str, ...] = tuple(raw["coarse_7"])
        self.second_6: dict[int, str] = {int(k): str(v) for k, v in raw["second_6"].items()}
        self.worldcover: dict[int, dict[str, Any]] = {
            int(k): v for k, v in raw["worldcover_to_coarse7"].items()
        }

        self._by_code = {c.code: c for c in self.classes}
        self._by_index = {c.index: c for c in self.classes}
        self.c19_names: tuple[str, ...] = tuple(
            sorted({c.to_19 for c in self.classes if c.to_19})
        )
        self._c19_id = {n: i for i, n in enumerate(self.c19_names)}
        self._coarse7_id = {n: i for i, n in enumerate(self.coarse_7)}

        self._validate()

    # ---------------------------------------------------------------- validation
    def _validate(self) -> None:
        indices = [c.index for c in self.classes]
        if indices != list(range(len(self.classes))):
            raise TaxonomyError(
                "training indices must be contiguous from 0",
                count=len(self.classes), first_bad=next(
                    (i for i, v in enumerate(indices) if i != v), None),
            )
        if len({c.code for c in self.classes}) != len(self.classes):
            raise TaxonomyError("duplicate CORINE code", count=len(self.classes))
        for c in self.classes:
            if c.l2 not in self.level_2:
                raise TaxonomyError("unknown L2 parent", code=c.code, l2=c.l2)
            if c.l1 not in self.level_1:
                raise TaxonomyError("unknown L1 parent", code=c.code, l1=c.l1)
            if c.to_coarse7 not in self._coarse7_id:
                raise TaxonomyError("unknown coarse-7 target", code=c.code, target=c.to_coarse7)
            if c.l2 // 10 != c.l1:
                raise TaxonomyError("L2 is not nested under its L1", code=c.code, l2=c.l2, l1=c.l1)
            if c.code // 10 != c.l2:
                raise TaxonomyError("L3 is not nested under its L2", code=c.code, l2=c.l2)

    # ---------------------------------------------------------------- lookups
    def by_code(self, code: int) -> ClassEntry:
        """Look up a class by CORINE code.

        Raises:
            TaxonomyError: If the code is not one of the 44 classes.
        """
        try:
            return self._by_code[int(code)]
        except KeyError as exc:
            raise TaxonomyError(
                "unknown CORINE code", code=int(code),
                hint="999 is unclassified, not a class",
            ) from exc

    def by_index(self, index: int) -> ClassEntry:
        """Look up a class by contiguous training index."""
        try:
            return self._by_index[int(index)]
        except KeyError as exc:
            raise TaxonomyError("unknown training index", index=int(index),
                                valid_range=f"0..{len(self.classes) - 1}") from exc

    def siblings(self, code: int) -> tuple[int, ...]:
        """Codes sharing this class's Level-2 parent, excluding itself.

        These are the confusions the benchmark's adversarial "no" answers exploit
        (IMPLEMENTATION_MAP §1.4), so they carry the lower `L_hier` weight.
        """
        entry = self.by_code(code)
        return tuple(c.code for c in self.classes if c.l2 == entry.l2 and c.code != entry.code)

    def l1_branch(self, code: int) -> tuple[int, ...]:
        """All codes sharing this class's Level-1 branch, including itself."""
        entry = self.by_code(code)
        return tuple(c.code for c in self.classes if c.l1 == entry.l1)

    # ---------------------------------------------------------------- conversion
    def codes_to_indices(self, code_map: IntArray) -> IntArray:
        """Map a CORINE-code array to contiguous training indices.

        Unclassified (999) becomes :data:`UNCLASSIFIED`.
        """
        out = np.full(code_map.shape, UNCLASSIFIED, dtype=np.int16)
        for c in self.classes:
            out[code_map == c.code] = c.index
        unknown = (out == UNCLASSIFIED) & (code_map != self.unclassified_code)
        if unknown.any():
            raise TaxonomyError(
                "class map contains codes outside the taxonomy",
                offending=sorted({int(v) for v in np.unique(code_map[unknown])})[:10],
            )
        return out

    def indices_to_codes(self, index_map: IntArray) -> IntArray:
        """Map contiguous training indices back to CORINE codes."""
        out = np.full(index_map.shape, self.unclassified_code, dtype=np.int32)
        for c in self.classes:
            out[index_map == c.index] = c.code
        return out

    # ---------------------------------------------------------------- aggregation
    def _target_of(self, entry: ClassEntry, level: Level) -> int:
        if level == "l3":
            return entry.index
        if level == "l2":
            return entry.l2
        if level == "l1":
            return entry.l1
        if level == "coarse7":
            return self._coarse7_id[entry.to_coarse7]
        if level == "c19":
            return self._c19_id[entry.to_19] if entry.to_19 else NO_EQUIVALENT
        raise TaxonomyError("unknown level", level=level, valid=list(LEVELS))

    def to_level(self, class_map: IntArray, level: Level) -> IntArray:
        """Aggregate a CORINE-code map to the requested level.

        Args:
            class_map: Integer array of CORINE codes (999 permitted for unclassified).
            level: One of :data:`LEVELS`.

        Returns:
            Integer array in the target level's id space. Unclassified pixels become
            :data:`UNCLASSIFIED`; pixels whose class has no counterpart at ``level`` become
            :data:`NO_EQUIVALENT` (only possible for ``"c19"``).

        Raises:
            TaxonomyError: If ``level`` is unknown or the map contains codes outside the
                taxonomy.
        """
        if level not in LEVELS:
            raise TaxonomyError("unknown level", level=level, valid=list(LEVELS))

        arr = np.asarray(class_map)
        out = np.full(arr.shape, UNCLASSIFIED, dtype=np.int16)
        seen = np.zeros(arr.shape, dtype=bool)
        for c in self.classes:
            hit = arr == c.code
            if hit.any():
                out[hit] = self._target_of(c, level)
                seen |= hit
        seen |= arr == self.unclassified_code
        if not seen.all():
            raise TaxonomyError(
                "class map contains codes outside the taxonomy",
                offending=sorted({int(v) for v in np.unique(arr[~seen])})[:10],
            )
        return out

    def mask_for(
        self, class_map: IntArray, class_query: str | int, level: Level
    ) -> npt.NDArray[np.bool_]:
        """Binary mask for one class at a requested level.

        **This is the aggregation-before-geometry guarantee in code.** The map is aggregated to
        ``level`` first, then the mask is taken. Connected components run on the returned mask,
        so continuous + discontinuous urban fabric yield ONE region, never two.

        Args:
            class_map: Integer array of CORINE codes.
            class_query: Class name at ``level``, or a CORINE code / L1 / L2 id.
            level: The level the query is posed at.

        Returns:
            Boolean array, True where the aggregated map equals the queried class.

        Raises:
            TaxonomyError: If the query cannot be resolved at ``level``.
        """
        target = self.resolve_query(class_query, level)
        mask: npt.NDArray[np.bool_] = self.to_level(class_map, level) == target
        return mask

    def resolve_query(self, class_query: str | int, level: Level) -> int:
        """Resolve a class name or id to its integer id at ``level``."""
        if level not in LEVELS:
            raise TaxonomyError("unknown level", level=level, valid=list(LEVELS))

        if isinstance(class_query, int) or (
            isinstance(class_query, str) and class_query.isdigit()
        ):
            value = int(class_query)
            if level == "l3":
                return self.by_code(value).index if value > 43 else value
            if level in ("l1", "l2"):
                table = self.level_1 if level == "l1" else self.level_2
                if value not in table:
                    raise TaxonomyError("unknown group id", level=level, id=value)
                return value
            raise TaxonomyError("numeric query is not meaningful at this level", level=level)

        name = str(class_query).strip()
        if level == "c19":
            if name not in self._c19_id:
                raise TaxonomyError(
                    "not a 19-class name", query=name,
                    hint="11 CORINE L3 classes have no 19-class equivalent",
                )
            return self._c19_id[name]
        if level == "coarse7":
            if name not in self._coarse7_id:
                raise TaxonomyError("not a coarse-7 name", query=name, valid=list(self.coarse_7))
            return self._coarse7_id[name]
        if level == "l3":
            for c in self.classes:
                if c.name.lower() == name.lower():
                    return c.index
            raise TaxonomyError("not an L3 class name", query=name)
        table = self.level_1 if level == "l1" else self.level_2
        for k, v in table.items():
            if v.lower() == name.lower():
                return k
        raise TaxonomyError("not a group name at this level", level=level, query=name)

    # ---------------------------------------------------------------- loss support
    def hierarchy_penalty_matrix(self) -> npt.NDArray[np.float32]:
        """44x44 confusion penalty matrix for `L_hier` (CLAUDE.md §1).

        Entry ``[i, j]`` is the multiplier applied when true class ``i`` is predicted as ``j``:

        - ``0.0`` on the diagonal — a correct prediction is not penalised.
        - :data:`SIBLING_PENALTY` (1.0) within a Level-1 branch.
        - :data:`CROSS_L1_PENALTY` (1.5) across Level-1 branches, because the benchmark's
          adversarial "no" answers are built from semantically similar classes and crossing a
          top-level branch is the more serious error.

        Returns:
            Symmetric float array of shape (44, 44) with a zero diagonal.
        """
        l1 = np.array([c.l1 for c in sorted(self.classes, key=lambda c: c.index)])
        same_l1 = l1[:, None] == l1[None, :]
        matrix: npt.NDArray[np.float32] = np.where(
            same_l1, SIBLING_PENALTY, CROSS_L1_PENALTY
        ).astype(np.float32)
        np.fill_diagonal(matrix, 0.0)
        return matrix


@lru_cache(maxsize=1)
def load_taxonomy(path: Path | None = None) -> Taxonomy:
    """Load and validate the CORINE nomenclature.

    Args:
        path: Nomenclature YAML. Defaults to ``configs/taxonomy/corine_l3.yaml``.

    Returns:
        A validated :class:`Taxonomy`.

    Raises:
        TaxonomyError: If the file is missing or fails structural validation.
    """
    target = path if path is not None else project_root() / NOMENCLATURE
    if not target.is_file():
        raise TaxonomyError("taxonomy nomenclature not found", path=str(target))
    raw: dict[str, Any] = yaml.safe_load(target.read_text(encoding="utf-8"))
    return Taxonomy(raw)
