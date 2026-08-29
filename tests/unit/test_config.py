"""Configuration loads and validates; invalid configuration raises a typed error."""

from __future__ import annotations

from pathlib import Path

import pytest

from satquery.config.loader import load_config, load_yaml
from satquery.config.schema import Config
from satquery.exceptions import ConfigError, SatQueryError

pytestmark = pytest.mark.unit


class TestValidConfig:
    def test_real_config_loads_and_validates(self, config: Config) -> None:
        assert isinstance(config, Config)
        assert config.project.name == "satquery"
        assert config.project.seed >= 0

    def test_frozen_architecture_facts_survive_loading(self, config: Config) -> None:
        """CLAUDE.md §1 values must arrive intact through the YAML round trip."""
        assert config.taxonomy.num_classes == 44
        assert config.preprocessing.in_channels == 12
        assert config.m1.num_classes == 44
        assert config.m1.pretrained is False, "M1 trains from scratch by default"
        assert config.data.patch_size == 120
        assert config.data.split_strategy == "geographic_block"

    def test_m1_loss_weights_match_the_frozen_composition(self, config: Config) -> None:
        """L_CE + 0.5*L_Lovasz + 0.3*L_hier + 0.2*L_scale."""
        assert config.m1.loss_ce_weight == 1.0
        assert config.m1.loss_lovasz_weight == 0.5
        assert config.m1.loss_hierarchy_weight == 0.3
        assert config.m1.loss_scale_weight == 0.2

    def test_mixup_and_cutmix_are_off(self, config: Config) -> None:
        """CLAUDE.md §1: they corrupt connected-component logic."""
        assert config.preprocessing.use_mixup is False
        assert config.preprocessing.use_cutmix is False

    def test_m2_fitted_parameters_are_unset(self, config: Config) -> None:
        """The four S8-fitted parameters must not carry guessed defaults."""
        assert config.m2.connectivity is None
        assert config.m2.min_mapping_unit_px is None
        assert config.m2.opening_kernel_px is None
        assert config.m2.adjacency_dilation_px is None
        assert config.m2.is_fitted is False

    def test_config_is_immutable(self, config: Config) -> None:
        with pytest.raises((TypeError, ValueError)):
            config.project.seed = 99  # type: ignore[misc]

    def test_overrides_apply_over_files(self, real_config_dir: Path) -> None:
        overridden = load_config(
            config_dir=real_config_dir,
            overrides={"project": {"seed": 4242}},
        )
        assert overridden.project.seed == 4242


class TestInvalidConfig:
    def test_missing_directory_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_path / "does-not-exist")
        assert "config directory not found" in info.value.message

    def test_malformed_yaml_raises_config_error(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "project.yaml").write_text("key: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_config_dir)
        assert "not valid YAML" in info.value.message

    def test_non_mapping_yaml_raises_config_error(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "project.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_config_dir)
        assert "mapping at the top level" in info.value.message

    def test_missing_required_field_raises_config_error(self, tmp_config_dir: Path) -> None:
        """`project` has required fields (stage, seed) with no defaults."""
        (tmp_config_dir / "project.yaml").write_text("name: satquery\n", encoding="utf-8")
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_config_dir)
        assert info.value.context["error_count"] >= 1
        fields = {p["field"] for p in info.value.context["problems"]}
        assert {"project.stage", "project.seed"} <= fields

    def test_unknown_key_is_rejected(self, tmp_config_dir: Path) -> None:
        """extra='forbid': a typo must fail loudly, not be silently ignored."""
        (tmp_config_dir / "project.yaml").write_text(
            "stage: S1\nseed: 1\nnaem: typo\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_config_dir)
        fields = {p["field"] for p in info.value.context["problems"]}
        assert "project.naem" in fields

    def test_out_of_range_seed_is_rejected(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "project.yaml").write_text("stage: S1\nseed: -5\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(config_dir=tmp_config_dir)

    def test_wrong_channel_count_is_rejected(self, tmp_config_dir: Path) -> None:
        """Dropping a band must fail validation, not silently reach M1."""
        (tmp_config_dir / "project.yaml").write_text("stage: S1\nseed: 1\n", encoding="utf-8")
        (tmp_config_dir / "preprocessing.yaml").write_text(
            "s1_bands: [VV]\ns2_bands: [B02, B03, B04]\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError) as info:
            load_config(config_dir=tmp_config_dir)
        assert any("12 channels" in p["problem"] for p in info.value.context["problems"])

    def test_random_split_is_rejected(self, tmp_config_dir: Path) -> None:
        """CLAUDE.md §1 forbids random splits — geographic leakage."""
        (tmp_config_dir / "project.yaml").write_text("stage: S1\nseed: 1\n", encoding="utf-8")
        (tmp_config_dir / "data.yaml").write_text("split_strategy: random\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(config_dir=tmp_config_dir)

    def test_enabling_mixup_is_rejected(self, tmp_config_dir: Path) -> None:
        (tmp_config_dir / "project.yaml").write_text("stage: S1\nseed: 1\n", encoding="utf-8")
        (tmp_config_dir / "preprocessing.yaml").write_text("use_mixup: true\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(config_dir=tmp_config_dir)

    def test_changing_class_count_is_rejected(self, tmp_config_dir: Path) -> None:
        """The 19-class scheme is not the segmentation target."""
        (tmp_config_dir / "project.yaml").write_text("stage: S1\nseed: 1\n", encoding="utf-8")
        (tmp_config_dir / "taxonomy.yaml").write_text("num_classes: 19\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(config_dir=tmp_config_dir)

    def test_config_error_is_a_satquery_error(self, tmp_path: Path) -> None:
        with pytest.raises(SatQueryError):
            load_config(config_dir=tmp_path / "nope")


class TestLoadYaml:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            load_yaml(tmp_path / "absent.yaml")

    def test_empty_file_yields_empty_mapping(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        assert load_yaml(path) == {}
