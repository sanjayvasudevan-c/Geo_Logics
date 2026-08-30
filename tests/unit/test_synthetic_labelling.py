"""CLAUDE.md §7's SYNTHETIC labelling rule is enforced in CI, not followed by habit.

§7: "Synthetic data is allowed only for unit tests, pipeline tests, stress tests, and edge
cases, and must be labelled SYNTHETIC in filename and docstring."

A convention nobody checks decays. This is the same escalation applied to the rasterio-only
rule: move it from documented to tested, so a future contributor cannot quietly add a module
that fabricates data without saying so.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS_ROOT = Path(__file__).resolve().parents[1]

#: Markers that a module fabricates data rather than reading real corpora.
FABRICATION_MARKERS = (
    "write_synthetic_raster",   # builds GeoTIFFs
    "np.array([[",              # inline hand-built arrays
    "np.full((",
    "np.zeros((",
    "np.arange(",
)


def _modules_that_fabricate() -> list[Path]:
    """Test modules that construct data instead of loading it."""
    found = []
    for path in sorted(TESTS_ROOT.rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in FABRICATION_MARKERS):
            found.append(path)
    return found


def _module_docstring(path: Path) -> str:
    return ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""


class TestSyntheticLabelling:
    def test_at_least_one_module_fabricates(self) -> None:
        """Guard against the detector silently matching nothing and passing vacuously."""
        assert _modules_that_fabricate(), "detector found no fabricating modules — it is broken"

    def test_every_fabricating_module_says_SYNTHETIC_in_its_docstring(self) -> None:
        unlabelled = [
            p.relative_to(TESTS_ROOT).as_posix()
            for p in _modules_that_fabricate()
            if "SYNTHETIC" not in _module_docstring(p)
        ]
        assert not unlabelled, (
            "CLAUDE.md §7 requires synthetic data to be labelled SYNTHETIC in the docstring; "
            f"unlabelled: {unlabelled}"
        )

    def test_every_fabricating_module_has_a_docstring_at_all(self) -> None:
        missing = [
            p.relative_to(TESTS_ROOT).as_posix()
            for p in _modules_that_fabricate()
            if not _module_docstring(p).strip()
        ]
        assert not missing, f"modules fabricating data with no docstring: {missing}"

    def test_the_raster_factory_is_filename_labelled(self) -> None:
        """§7 also requires the FILENAME to carry the label."""
        factory = TESTS_ROOT / "synthetic.py"
        assert factory.is_file(), "expected the SYNTHETIC raster factory at tests/synthetic.py"
        assert "synthetic" in factory.name.lower()
        assert "SYNTHETIC" in _module_docstring(factory)

    def test_all_geotiff_creation_is_funnelled_through_the_factory(self) -> None:
        """One labelled place builds rasters, so none can appear unlabelled elsewhere."""
        me = Path(__file__).name
        writers = []
        for path in TESTS_ROOT.rglob("*.py"):
            if path.name == me:      # this detector names the tokens it looks for
                continue
            text = path.read_text(encoding="utf-8")
            if "rasterio.open(" in text and '"w"' in text:
                writers.append(path.relative_to(TESTS_ROOT).as_posix())
        assert writers == ["synthetic.py"], (
            f"raster creation must stay in the labelled factory; also found: {writers}"
        )
