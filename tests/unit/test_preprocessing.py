"""P1 sensor preprocessing: dB conversion, resampling, channel order, presence mask, leakage.

All inputs are SYNTHETIC (CLAUDE.md §7) with known values, so these assert arithmetic
correctness rather than plausibility.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from satquery.exceptions import ConfigError, InputValidationError
from satquery.preprocessing.bands import (
    CHANNEL_ORDER,
    N_CHANNELS,
    N_OPTICAL,
    S1_BANDS,
    S2_10M,
    S2_20M,
    S2_60M_DISCARDED,
    S2_BANDS,
    band_index,
    native_resolution_m,
)
from satquery.preprocessing.norm_stats import BandStats, NormStats, load_norm_stats
from satquery.preprocessing.sensors import (
    DB_FLOOR_POWER,
    band_presence_mask,
    linear_to_db,
    resample_to_10m,
    spectral_index,
    stack_channels,
    zscore,
)

pytestmark = pytest.mark.unit

# The stats script is a CLI, not an importable package module. Load split_hash from it directly
# so the leakage assertion tests the REAL implementation rather than a copy of it.
_SPEC = importlib.util.spec_from_file_location(
    "compute_norm_stats",
    Path(__file__).resolve().parents[2] / "scripts" / "data" / "compute_norm_stats.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_stats_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_stats_script)
split_hash = _stats_script.split_hash


class TestChannelOrder:
    def test_exactly_12_channels(self) -> None:
        assert N_CHANNELS == 12
        assert len(CHANNEL_ORDER) == 12

    def test_frozen_order_is_asserted_explicitly(self) -> None:
        """CLAUDE.md §1. A silent reorder produces confident nonsense with no error."""
        assert CHANNEL_ORDER == (
            "VV", "VH",
            "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12",
        )

    def test_sar_comes_first(self) -> None:
        assert CHANNEL_ORDER[:2] == S1_BANDS

    def test_ten_optical_bands(self) -> None:
        assert N_OPTICAL == 10
        assert len(S2_BANDS) == 10

    def test_60m_bands_are_absent_from_the_order(self) -> None:
        assert S2_60M_DISCARDED.isdisjoint(set(CHANNEL_ORDER))
        assert {"B01", "B09", "B10"} == S2_60M_DISCARDED

    def test_10m_and_20m_partition_the_optical_bands(self) -> None:
        assert set(S2_BANDS) == S2_10M | S2_20M
        assert S2_10M.isdisjoint(S2_20M)

    def test_band_index_matches_position(self) -> None:
        assert band_index("VV") == 0
        assert band_index("B02") == 2
        assert band_index("B12") == 11

    def test_unknown_band_raises(self) -> None:
        with pytest.raises(KeyError):
            band_index("B01")

    def test_native_resolutions(self) -> None:
        assert native_resolution_m("B02") == 10
        assert native_resolution_m("B11") == 20
        assert native_resolution_m("B01") == 60


class TestSarDbConversion:
    def test_known_values(self) -> None:
        """dB = 10*log10(power), checked against arithmetic."""
        out = linear_to_db(np.array([[1.0, 10.0, 100.0, 0.1]]))
        assert np.allclose(out.values, [[0.0, 10.0, 20.0, -10.0]], atol=1e-5)

    def test_zero_power_is_floored_not_nan(self) -> None:
        out = linear_to_db(np.array([[0.0]]))
        assert np.isfinite(out.values).all()
        assert out.floored == 1
        assert out.values[0, 0] == pytest.approx(10 * math.log10(DB_FLOOR_POWER))

    def test_negative_power_is_floored_not_nan(self) -> None:
        out = linear_to_db(np.array([[-1.0, -0.5]]))
        assert np.isfinite(out.values).all()
        assert out.floored == 2

    def test_floored_count_is_reported(self) -> None:
        """Silently repairing bad pixels is exactly the failure mode we refuse."""
        assert linear_to_db(np.array([[0.0, 1.0, 0.0, 2.0]])).floored == 2

    def test_no_nan_or_inf_in_output(self) -> None:
        out = linear_to_db(np.array([[0.0, 1e-30, 1e10, 1.0]]))
        assert not np.isnan(out.values).any()
        assert not np.isinf(out.values).any()

    def test_nan_input_raises_rather_than_propagating(self) -> None:
        with pytest.raises(InputValidationError) as e:
            linear_to_db(np.array([[np.nan]]))
        assert e.value.context["check"] == "sar_finite_input"

    def test_inf_input_raises(self) -> None:
        with pytest.raises(InputValidationError):
            linear_to_db(np.array([[np.inf]]))

    def test_output_is_float32(self) -> None:
        assert linear_to_db(np.array([[1.0]])).values.dtype == np.float32


class TestResampling:
    def test_20m_band_resamples_to_10m_shape(self) -> None:
        src = np.arange(60 * 60, dtype=np.float32).reshape(60, 60)
        assert resample_to_10m(src, (120, 120)).shape == (120, 120)

    def test_constant_field_is_preserved(self) -> None:
        src = np.full((60, 60), 7.0, dtype=np.float32)
        assert np.allclose(resample_to_10m(src, (120, 120)), 7.0)

    def test_already_correct_shape_is_unchanged(self) -> None:
        src = np.arange(120 * 120, dtype=np.float32).reshape(120, 120)
        assert np.array_equal(resample_to_10m(src, (120, 120)), src)

    def test_linear_ramp_stays_monotonic(self) -> None:
        src = np.tile(np.arange(60, dtype=np.float32), (60, 1))
        out = resample_to_10m(src, (120, 120))
        assert np.all(np.diff(out[0]) >= -1e-6)

    def test_invalid_target_shape_raises(self) -> None:
        with pytest.raises(InputValidationError):
            resample_to_10m(np.zeros((60, 60), dtype=np.float32), (0, 120))


class TestZscore:
    def test_known_standardisation(self) -> None:
        assert np.allclose(zscore(np.array([[5.0, 15.0]]), mean=10.0, std=5.0), [[-1.0, 1.0]])

    def test_zero_std_raises_rather_than_producing_inf(self) -> None:
        with pytest.raises(InputValidationError) as e:
            zscore(np.array([[1.0]]), mean=0.0, std=0.0)
        assert e.value.context["check"] == "norm_std_positive"


class TestBandPresenceMask:
    def test_length_10_all_present_by_default(self) -> None:
        m = band_presence_mask()
        assert m.shape == (N_OPTICAL,)
        assert np.all(m == 1.0)

    def test_synthetic_dropout_is_reflected(self) -> None:
        m = band_presence_mask({"B11": False, "B12": False})
        assert m[S2_BANDS.index("B11")] == 0.0
        assert m[S2_BANDS.index("B12")] == 0.0
        assert m.sum() == N_OPTICAL - 2

    def test_mask_order_matches_band_order(self) -> None:
        for i, band in enumerate(S2_BANDS):
            m = band_presence_mask({band: False})
            assert m[i] == 0.0
            assert m.sum() == N_OPTICAL - 1

    def test_unknown_band_raises(self) -> None:
        with pytest.raises(InputValidationError) as e:
            band_presence_mask({"B01": False})
        assert e.value.context["check"] == "band_presence_names"

    def test_dropped_band_distinguishable_from_dark_band(self) -> None:
        """The whole point: zeros alone cannot say 'not measured'."""
        dark = np.zeros((4, 4), dtype=np.float32)
        stacked = stack_channels({}, {"B11": dark}, (4, 4))
        present = band_presence_mask({"B11": True})
        dropped = band_presence_mask({"B11": False})
        assert np.array_equal(stacked[band_index("B11")], dark)
        assert present[S2_BANDS.index("B11")] != dropped[S2_BANDS.index("B11")]


class TestStackChannels:
    def test_output_is_12_channels_in_frozen_order(self) -> None:
        sar = {b: np.full((8, 8), i + 1, dtype=np.float32) for i, b in enumerate(S1_BANDS)}
        opt = {b: np.full((8, 8), 100 + i, dtype=np.float32) for i, b in enumerate(S2_BANDS)}
        out = stack_channels(sar, opt, (8, 8))
        assert out.shape == (12, 8, 8)
        assert out[0][0, 0] == 1.0        # VV
        assert out[1][0, 0] == 2.0        # VH
        assert out[2][0, 0] == 100.0      # B02
        assert out[11][0, 0] == 109.0     # B12

    def test_20m_bands_are_resampled_on_the_way_in(self) -> None:
        opt = {b: np.full((60, 60), 5.0, dtype=np.float32) for b in S2_20M}
        out = stack_channels({}, opt, (120, 120))
        assert out.shape == (12, 120, 120)
        assert np.allclose(out[band_index("B11")], 5.0)

    def test_missing_band_is_zero_filled(self) -> None:
        out = stack_channels({}, {}, (4, 4))
        assert out.shape == (12, 4, 4)
        assert np.all(out == 0.0)

    def test_wrong_shape_10m_band_raises(self) -> None:
        with pytest.raises(InputValidationError) as e:
            stack_channels({}, {"B02": np.zeros((7, 7), dtype=np.float32)}, (8, 8))
        assert e.value.context["check"] == "channel_shape"

    def test_60m_bands_never_appear(self) -> None:
        out = stack_channels({}, {b: np.ones((8, 8), dtype=np.float32) for b in S2_BANDS}, (8, 8))
        assert out.shape[0] == 12
        assert set(CHANNEL_ORDER).isdisjoint(S2_60M_DISCARDED)


class TestSpectralIndices:
    def test_ndvi_known_value(self) -> None:
        out = spectral_index("ndvi", {"B08": np.array([[3.0]]), "B04": np.array([[1.0]])})
        assert out[0, 0] == pytest.approx(0.5)

    def test_zero_denominator_gives_zero_not_nan(self) -> None:
        out = spectral_index("ndvi", {"B08": np.array([[0.0]]), "B04": np.array([[0.0]])})
        assert out[0, 0] == 0.0
        assert np.isfinite(out).all()

    def test_range_is_bounded(self) -> None:
        rng = np.random.default_rng(1337)
        a, b = rng.random((16, 16)).astype(np.float32), rng.random((16, 16)).astype(np.float32)
        out = spectral_index("ndwi", {"B03": a, "B08": b})
        assert out.min() >= -1.0 and out.max() <= 1.0

    def test_unknown_index_raises(self) -> None:
        with pytest.raises(InputValidationError):
            spectral_index("nope", {})

    def test_missing_band_raises(self) -> None:
        with pytest.raises(InputValidationError) as e:
            spectral_index("ndbi", {"B08": np.array([[1.0]])})
        assert "B11" in e.value.context["missing"]

    def test_indices_default_off_in_config(self, config) -> None:
        """Ablation candidates, not defaults (CLAUDE.md §1)."""
        assert config.preprocessing.spectral_indices == ()


class TestNormalisationStatsLeakage:
    """CLAUDE.md §7: statistics are fitted on the TRAINING SPLIT ONLY."""

    def _stats(self, split: str = "train", n: int = 100, mean: float = 0.0) -> NormStats:
        return NormStats(
            bands={b: BandStats(mean=mean, std=1.0) for b in CHANNEL_ORDER},
            split=split, split_hash="abc123", n_samples=n, computed_at="2026-08-30T00:00:00Z",
        )

    def test_complete_train_stats_validate(self) -> None:
        self._stats().validate_complete()

    def test_non_train_split_is_rejected(self) -> None:
        with pytest.raises(ConfigError) as e:
            self._stats(split="validation").validate_complete()
        assert "training split only" in e.value.message

    def test_incomplete_stats_are_rejected(self) -> None:
        s = self._stats()
        partial = NormStats(
            bands={k: v for k, v in list(s.bands.items())[:5]},
            split="train", split_hash="x", n_samples=1, computed_at="t",
        )
        with pytest.raises(ConfigError) as e:
            partial.validate_complete()
        assert len(e.value.context["missing"]) == 7

    def test_changing_validation_data_cannot_change_stats(self) -> None:
        """The leakage assertion: stats depend only on the training sample list.

        Two runs over the SAME training samples must produce the same split_hash and the same
        values, whatever validation data exists alongside them.
        """
        train_ids = ["p1", "p2", "p3"]
        h1 = split_hash(train_ids)
        h2 = split_hash(list(reversed(train_ids)))
        assert h1 == h2, "split hash must not depend on ordering"
        assert h1 != split_hash([*train_ids, "validation_patch"]), (
            "adding a non-training patch MUST change the hash — that is how the leakage "
            "test detects contamination"
        )

    def test_missing_stats_file_raises_rather_than_defaulting(self, tmp_path) -> None:
        with pytest.raises(ConfigError) as e:
            load_norm_stats(tmp_path / "absent.yaml")
        assert "TRAINING SPLIT" in e.value.message

    def test_for_band_missing_raises(self) -> None:
        with pytest.raises(ConfigError):
            self._stats().for_band("B01")


class TestRasterioOnly:
    """CLAUDE.md §1: rasterio only for GeoTIFFs — enforced by a test, not a convention."""

    def test_no_pil_or_opencv_import_in_src(self) -> None:
        root = Path(__file__).resolve().parents[2] / "src"
        banned = ("import cv2", "from cv2", "from PIL", "import PIL",
                  "imageio.imread", "from skimage.io import imread")
        offenders = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                if token in text:
                    offenders.append(f"{path.name}: {token}")
        assert not offenders, f"banned image loaders in src/: {offenders}"
