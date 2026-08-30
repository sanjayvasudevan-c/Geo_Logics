"""Typed configuration schema.

CLAUDE.md §8: "All important parameters live in ``configs/*.yaml``. No magic numbers in
``src/``." This module defines the Pydantic models those files are validated against.

Every model sets ``extra="forbid"``. A typo in a YAML key is a loud failure, not a silently
ignored setting — silent config drift is exactly the class of error that produces a confident
wrong number with a clean-looking trace (IMPLEMENTATION_MAP §5.3).

Values that the architecture freezes (CLAUDE.md §1) are constrained here so that a drifting
edit fails validation rather than reaching a model: the 44-class CORINE L3 taxonomy, the 12
input channels, the 120x120 patch, the M1 loss weights, and the ban on mixup/cutmix.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "Config",
    "DataConfig",
    "EvalConfig",
    "LoggingConfig",
    "M1Config",
    "M2Config",
    "PreprocessingConfig",
    "ProjectConfig",
    "TaxonomyConfig",
]


class _Base(BaseModel):
    """Common strictness for every config model."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ProjectConfig(_Base):
    """Top-level project identity and reproducibility settings."""

    name: str = "satquery"
    stage: str = Field(description="Current stage identifier, e.g. 'S1'.")
    seed: int = Field(ge=0, le=2**32 - 1, description="Global seed (CLAUDE.md §8).")
    deterministic: bool = True


class LoggingConfig(_Base):
    """Structured logging settings."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_output: bool = True
    redact_external_paths: bool = True


class DataConfig(_Base):
    """Dataset roots and split policy."""

    raw_dir: str = "data/raw"
    interim_dir: str = "data/interim"
    processed_dir: str = "data/processed"

    patch_size: int = Field(default=120, ge=1, description="reBEN patch edge in pixels.")
    gsd_metres: float = Field(default=10.0, gt=0, description="Ground sample distance.")

    # CLAUDE.md §1: geographic block CV, k=5. Never a random split.
    split_strategy: Literal["geographic_block"] = "geographic_block"
    cv_folds: int = Field(default=5, ge=2)
    block_by: Literal["country", "grid_1deg", "s2_tile"] = "country"

    # CLAUDE.md §7: the benchmark split is sealed.
    benchmark_split_guard_env: str = "ALLOW_BENCHMARK_EVAL"

    @field_validator("split_strategy")
    @classmethod
    def _no_random_split(cls, value: str) -> str:
        if value != "geographic_block":
            raise ValueError(
                "CLAUDE.md §1 mandates geographic block CV; random splits leak across "
                "spatially autocorrelated patches"
            )
        return value


class PreprocessingConfig(_Base):
    """Sensor normalisation and augmentation (pipeline stage 2)."""

    # CLAUDE.md §1: S1 (VV, VH) = 2 channels, S2 = 10 channels, total 12.
    s1_bands: tuple[str, ...] = ("VV", "VH")
    s2_bands: tuple[str, ...] = (
        "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12",
    )

    s1_to_db: bool = True
    resample_20m_to_10m: Literal["bilinear"] = "bilinear"
    discard_60m_bands: bool = True

    normalisation: Literal["train_split_zscore"] = "train_split_zscore"
    band_presence_mask: bool = True
    spectral_indices: tuple[str, ...] = ()

    # CLAUDE.md §1 forbids mixup/cutmix: they corrupt connected-component logic.
    use_mixup: Literal[False] = False
    use_cutmix: Literal[False] = False

    @property
    def in_channels(self) -> int:
        """Total input channels reaching M1."""
        return len(self.s1_bands) + len(self.s2_bands)

    @model_validator(mode="after")
    def _check_channel_count(self) -> PreprocessingConfig:
        if self.in_channels != 12:
            raise ValueError(
                f"CLAUDE.md §1 freezes M1 input at 12 channels "
                f"(2 SAR + 10 optical); got {self.in_channels}"
            )
        return self


class TaxonomyConfig(_Base):
    """CORINE hierarchy settings (M2 step 0 — hierarchy aggregation)."""

    # CLAUDE.md §1: CORINE Level-3, 44 classes. The 19-class scheme is image-level only.
    primary: Literal["corine_l3"] = "corine_l3"
    num_classes: Literal[44] = 44
    aggregation_table: str = "configs/taxonomy/corine_hierarchy.yaml"

    auxiliary_heads: tuple[str, ...] = ("corine_l3_19", "coarse_7")
    ignore_index: int = Field(default=255, ge=0, le=255)
    coarse_7_classes: tuple[str, ...] = (
        "built_up", "cropland", "tree_cover", "grassland_shrub",
        "water", "bare_sparse", "wetland",
    )


class M1Config(_Base):
    """M1 — multi-sensor LULC segmenter."""

    architecture: Literal["dual_encoder_unet"] = "dual_encoder_unet"
    encoder: str = "convnextv2_tiny"
    fusion: Literal["conv1x1_se_gate"] = "conv1x1_se_gate"
    num_classes: Literal[44] = 44
    # CLAUDE.md §1: from scratch. ImageNet init is an ablation, not the default.
    pretrained: bool = False

    # CLAUDE.md §1: L_CE + 0.5*L_Lovasz + 0.3*L_hier + 0.2*L_scale
    loss_ce_weight: float = Field(default=1.0, ge=0)
    loss_lovasz_weight: float = Field(default=0.5, ge=0)
    loss_hierarchy_weight: float = Field(default=0.3, ge=0)
    loss_scale_weight: float = Field(default=0.2, ge=0)

    tta_transforms: int = Field(default=8, ge=1)


class M2Config(_Base):
    """M2 — symbolic geometry engine. Deterministic logic, fitted parameters.

    The four fitted parameters default to ``None``: they are *recovered* from ground-truth
    maps at S8, not guessed. A geometry call with an unfitted parameter must raise
    ``GeometryError`` rather than silently using a plausible default — CLAUDE.md §5.
    """

    # CLAUDE.md §1: scipy.ndimage + skimage.measure. No neural network.
    implementation: Literal["scipy_skimage"] = "scipy_skimage"

    connectivity: Literal[4, 8] | None = None
    min_mapping_unit_px: int | None = Field(default=None, ge=0)
    opening_kernel_px: int | None = Field(default=None, ge=0)
    adjacency_dilation_px: int | None = Field(default=None, ge=0)

    # GR-2 (S3): area is decile-quantised, not rounded. 11 bins over patch coverage.
    area_bins: Literal[11] = 11
    patch_area_m2: int = Field(default=1_440_000, gt=0)
    # Resolved in DIRECTION at S3 (standard semantics), to be CONFIRMED at S7 against
    # computed truth. None until then — a guessed rule would silently mis-bin boundary cases.
    bin_boundary_rule: Literal["inclusive_lower_exclusive_upper", "inclusive_both"] | None = None

    tier_primary_min: float = Field(default=0.25, gt=0, lt=1)
    tier_secondary_min: float = Field(default=0.05, gt=0, lt=1)
    referring_area_min: float = Field(default=0.01, gt=0, lt=1)
    referring_area_max: float = Field(default=0.50, gt=0, le=1)
    referring_bbox_fill_min: float = Field(default=0.40, gt=0, le=1)

    @model_validator(mode="after")
    def _check_thresholds(self) -> M2Config:
        if self.tier_secondary_min >= self.tier_primary_min:
            raise ValueError("tier_secondary_min must be below tier_primary_min")
        if self.referring_area_min >= self.referring_area_max:
            raise ValueError("referring_area_min must be below referring_area_max")
        return self

    @property
    def is_fitted(self) -> bool:
        """Whether the four S8-fitted parameters have all been supplied."""
        return None not in (
            self.connectivity,
            self.min_mapping_unit_px,
            self.opening_kernel_px,
            self.adjacency_dilation_px,
        )


class EvalConfig(_Base):
    """Evaluation protocol (IMPLEMENTATION_MAP §8.3)."""

    bootstrap_resamples: int = Field(default=1000, ge=100)
    # Resample over image pairs, never over annotations: annotations within a pair correlate.
    bootstrap_unit: Literal["image_pair"] = "image_pair"
    confidence_level: float = Field(default=0.95, gt=0, lt=1)

    paired_test: Literal["mcnemar"] = "mcnemar"

    # The significance floor. Differences below these are not claimable.
    min_claimable_delta_binary_pts: float = Field(default=3.0, gt=0)
    min_claimable_delta_mcq_pts: float = Field(default=4.0, gt=0)

    # Blind baselines are mandatory (IMPLEMENTATION_MAP §8.3 item 3).
    require_blind_baselines: Literal[True] = True
    baselines: tuple[str, ...] = ("question_only", "majority_class", "class_prior")


class Config(_Base):
    """The single typed configuration object for the whole system.

    Assembled by :func:`satquery.config.loader.load_config` from the hierarchical YAML in
    ``configs/``. Nothing in ``src/`` reads a YAML file directly.
    """

    project: ProjectConfig
    logging: LoggingConfig = LoggingConfig()
    data: DataConfig = DataConfig()
    preprocessing: PreprocessingConfig = PreprocessingConfig()
    taxonomy: TaxonomyConfig = TaxonomyConfig()
    m1: M1Config = M1Config()
    m2: M2Config = M2Config()
    eval: EvalConfig = EvalConfig()
