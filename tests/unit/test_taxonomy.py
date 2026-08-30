"""Taxonomy layer: nomenclature integrity, aggregation, penalty matrix, synonyms.

The load-bearing test here is `test_adjacent_subclasses_aggregate_to_one_component`: it is the
aggregation-before-geometry guarantee, and IMPLEMENTATION_MAP §5.3 ranks getting it wrong as
the second most damaging silent failure in the system.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from satquery.exceptions import TaxonomyError
from satquery.taxonomy.core import (
    CROSS_L1_PENALTY,
    LEVELS,
    NO_EQUIVALENT,
    SIBLING_PENALTY,
    UNCLASSIFIED,
    load_taxonomy,
)
from satquery.taxonomy.synonyms import load_synonyms

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


@pytest.fixture(scope="module")
def syn():
    return load_synonyms()


class TestNomenclature:
    def test_all_44_l3_classes_present(self, tax) -> None:
        assert len(tax.classes) == 44

    def test_indices_are_unique_and_contiguous(self, tax) -> None:
        indices = sorted(c.index for c in tax.classes)
        assert indices == list(range(44))

    def test_codes_are_unique(self, tax) -> None:
        assert len({c.code for c in tax.classes}) == 44

    def test_every_class_maps_to_exactly_one_l2_l1_coarse7(self, tax) -> None:
        for c in tax.classes:
            assert c.l2 in tax.level_2
            assert c.l1 in tax.level_1
            assert c.to_coarse7 in tax.coarse_7

    def test_hierarchy_is_nested_by_code_arithmetic(self, tax) -> None:
        """CORINE codes encode their own parents: 311 -> L2 31 -> L1 3."""
        for c in tax.classes:
            assert c.code // 10 == c.l2
            assert c.l2 // 10 == c.l1

    def test_unclassified_is_999_and_ignored(self, tax) -> None:
        assert tax.unclassified_code == 999
        assert 999 not in {c.code for c in tax.classes}

    def test_exactly_19_distinct_c19_classes(self, tax) -> None:
        assert len(tax.c19_names) == 19

    def test_l3_to_19_is_partial_by_design(self, tax) -> None:
        """11 CORINE classes have no 19-class counterpart. That is a property, not a gap."""
        unmapped = [c.code for c in tax.classes if c.to_19 is None]
        assert len(unmapped) == 11
        assert set(unmapped) == {122, 123, 124, 131, 132, 133, 141, 142, 332, 334, 335}

    def test_seven_coarse_classes(self, tax) -> None:
        assert len(tax.coarse_7) == 7

    def test_worldcover_and_second_tables_present(self, tax) -> None:
        assert len(tax.worldcover) == 11
        assert len(tax.second_6) == 6
        for spec in tax.worldcover.values():
            assert spec["coarse7"] in tax.coarse_7


class TestLookups:
    def test_by_code_and_index_agree(self, tax) -> None:
        entry = tax.by_code(312)
        assert entry.name == "Coniferous forest"
        assert tax.by_index(entry.index).code == 312

    def test_unknown_code_raises(self, tax) -> None:
        with pytest.raises(TaxonomyError):
            tax.by_code(777)

    def test_999_is_not_a_class(self, tax) -> None:
        with pytest.raises(TaxonomyError) as info:
            tax.by_code(999)
        assert "unclassified" in str(info.value).lower()

    def test_siblings_share_l2_and_exclude_self(self, tax) -> None:
        assert set(tax.siblings(311)) == {312, 313}
        assert 311 not in tax.siblings(311)

    def test_l1_branch_includes_self(self, tax) -> None:
        branch = tax.l1_branch(311)
        assert 311 in branch
        assert all(tax.by_code(c).l1 == 3 for c in branch)
        assert 111 not in branch


class TestAggregation:
    def test_to_level_l1(self, tax) -> None:
        m = np.array([[111, 211], [311, 511]])
        assert np.array_equal(tax.to_level(m, "l1"), np.array([[1, 2], [3, 5]]))

    def test_to_level_l2(self, tax) -> None:
        m = np.array([[111, 112], [311, 312]])
        assert np.array_equal(tax.to_level(m, "l2"), np.array([[11, 11], [31, 31]]))

    def test_unclassified_propagates_as_sentinel(self, tax) -> None:
        m = np.array([[999, 111]])
        out = tax.to_level(m, "l1")
        assert out[0, 0] == UNCLASSIFIED
        assert out[0, 1] == 1

    def test_no_19_equivalent_is_explicit(self, tax) -> None:
        """Airports (124) must NOT be silently folded into a neighbouring 19-class."""
        out = tax.to_level(np.array([[124, 111]]), "c19")
        assert out[0, 0] == NO_EQUIVALENT
        assert out[0, 1] == tax.resolve_query("Urban fabric", "c19")

    def test_roundtrip_coarse7_pixel_counts(self, tax) -> None:
        """Synthetic map -> coarse-7 gives exactly the expected pixel counts."""
        m = np.array([
            [111, 111, 211, 211],   # 2 built_up, 2 cropland
            [311, 311, 511, 511],   # 2 tree_cover, 2 water
            [231, 231, 411, 411],   # 2 grassland_shrub, 2 wetland
            [331, 331, 999, 999],   # 2 bare_sparse, 2 unclassified
        ])
        out = tax.to_level(m, "coarse7")
        counts = {name: int((out == i).sum()) for i, name in enumerate(tax.coarse_7)}
        assert counts == {
            "built_up": 2, "cropland": 2, "tree_cover": 2,
            "grassland_shrub": 2, "water": 2, "bare_sparse": 2, "wetland": 2,
        }
        assert int((out == UNCLASSIFIED).sum()) == 2
        assert sum(counts.values()) + 2 == m.size

    def test_unknown_code_in_map_raises(self, tax) -> None:
        with pytest.raises(TaxonomyError) as info:
            tax.to_level(np.array([[111, 777]]), "l1")
        assert 777 in info.value.context["offending"]

    def test_unknown_level_raises(self, tax) -> None:
        with pytest.raises(TaxonomyError):
            tax.to_level(np.array([[111]]), "l9")  # type: ignore[arg-type]

    @pytest.mark.parametrize("level", LEVELS)
    def test_every_level_runs(self, tax, level) -> None:
        assert tax.to_level(np.array([[111, 312, 523]]), level).shape == (1, 3)


class TestAggregationBeforeGeometry:
    """The guarantee: aggregate FIRST, then run connected components."""

    def test_adjacent_subclasses_aggregate_to_one_component(self, tax) -> None:
        """Continuous (111) + discontinuous (112) urban fabric side by side is ONE region.

        This is the failure IMPLEMENTATION_MAP §5.3 ranks second most damaging: counting a city
        as two regions because its L3 subclasses differ.
        """
        m = np.array([
            [111, 111, 112, 112],
            [111, 111, 112, 112],
            [211, 211, 211, 211],
            [211, 211, 211, 211],
        ])

        # WRONG ORDER — components run per L3 class, before aggregating. This is what
        # "geometry before aggregation" actually looks like: each subclass is labelled on its
        # own, so the single city is counted once as 111 and again as 112.
        naive = sum(ndimage.label(m == code)[1] for code in (111, 112))
        assert naive == 2, "precondition: the naive order really does over-count"

        # RIGHT ORDER — aggregate to the queried level first, then run components.
        mask = tax.mask_for(m, "Urban fabric", "c19")
        _, correct = ndimage.label(mask)
        assert correct == 1, "aggregation-before-geometry must yield ONE urban region"

    def test_same_guarantee_at_l1(self, tax) -> None:
        """Different L2 parents, same L1 branch: still one artificial-surfaces region."""
        m = np.array([
            [111, 121],   # urban fabric + industrial: different L2, same L1
            [131, 141],   # mine site + green urban: different L2, same L1
        ])
        _, n = ndimage.label(tax.mask_for(m, "Artificial surfaces", "l1"))
        assert n == 1

    def test_mask_for_returns_boolean(self, tax) -> None:
        mask = tax.mask_for(np.array([[111, 211]]), "Urban fabric", "c19")
        assert mask.dtype == bool
        assert mask.tolist() == [[True, False]]

    def test_querying_an_unmapped_class_at_19_raises(self, tax) -> None:
        """'Airports' is not expressible at the 19 level — an error, not an empty mask."""
        with pytest.raises(TaxonomyError):
            tax.mask_for(np.array([[124]]), "Airports", "c19")


class TestPenaltyMatrix:
    def test_shape_is_44x44(self, tax) -> None:
        assert tax.hierarchy_penalty_matrix().shape == (44, 44)

    def test_diagonal_is_zero(self, tax) -> None:
        assert np.allclose(np.diag(tax.hierarchy_penalty_matrix()), 0.0)

    def test_matrix_is_symmetric(self, tax) -> None:
        m = tax.hierarchy_penalty_matrix()
        assert np.allclose(m, m.T)

    def test_cross_l1_entries_are_1_5(self, tax) -> None:
        m = tax.hierarchy_penalty_matrix()
        i = tax.by_code(111).index   # Artificial surfaces
        j = tax.by_code(311).index   # Forest
        assert m[i, j] == pytest.approx(CROSS_L1_PENALTY)

    def test_within_l1_entries_are_1_0(self, tax) -> None:
        m = tax.hierarchy_penalty_matrix()
        i = tax.by_code(311).index
        j = tax.by_code(312).index   # sibling: same L2, same L1
        assert m[i, j] == pytest.approx(SIBLING_PENALTY)

    def test_only_two_off_diagonal_values(self, tax) -> None:
        m = tax.hierarchy_penalty_matrix()
        off = m[~np.eye(44, dtype=bool)]
        assert set(np.unique(off).tolist()) == {SIBLING_PENALTY, CROSS_L1_PENALTY}


class TestCodeIndexConversion:
    def test_roundtrip(self, tax) -> None:
        codes = np.array([[111, 312, 523], [999, 211, 411]])
        back = tax.indices_to_codes(tax.codes_to_indices(codes))
        assert np.array_equal(back, codes)

    def test_unclassified_maps_to_sentinel(self, tax) -> None:
        assert tax.codes_to_indices(np.array([[999]]))[0, 0] == UNCLASSIFIED


class TestSynonyms:
    def test_every_synonym_resolves_to_a_valid_class(self, tax, syn) -> None:
        """No synonym may point at a class the taxonomy does not have."""
        for form in syn.forms:
            res = syn.resolve(form)
            tax.resolve_query(res.canonical, res.level)   # raises if invalid

    def test_observed_forms_from_real_question_text(self, syn) -> None:
        for form in ["arable lands", "coniferous forests", "transitional woodlands or shrubs",
                     "inland waters", "marine waters", "urban fabric",
                     "beaches dunes or sands", "moors heathland or sclerophyllous vegetation"]:
            assert syn.resolve(form).observed is True, form

    def test_plural_and_comma_variants_resolve(self, syn) -> None:
        assert syn.resolve("arable land").canonical == syn.resolve("arable lands").canonical
        assert syn.resolve("Beaches, dunes, sands").canonical == "Beaches, dunes, sands"

    def test_unobserved_forms_are_flagged(self, syn) -> None:
        assert syn.resolve("built-up").observed is False

    def test_approximate_indian_forms_are_flagged(self, syn) -> None:
        res = syn.resolve("mangroves")
        assert res.approximate is True
        assert res.observed is False

    def test_unknown_form_raises_not_silently_dropped(self, syn) -> None:
        with pytest.raises(TaxonomyError) as info:
            syn.resolve("nuclear power station")
        assert "unresolved" in info.value.message

    def test_try_resolve_returns_none_for_unknown(self, syn) -> None:
        assert syn.try_resolve("nuclear power station") is None

    def test_no_unresolved_forms_remain(self, syn) -> None:
        """S4 requirement: unresolved surface forms are reported, not silently dropped."""
        assert syn.unresolved == []

    def test_default_level_is_c19(self, syn) -> None:
        """S3: questions are asked exclusively in the 19-class vocabulary."""
        assert syn.default_level == "c19"

    def test_all_19_classes_have_at_least_one_observed_form(self, tax, syn) -> None:
        covered = {
            syn.resolve(f).canonical for f in syn.forms if syn.resolve(f).observed
        }
        assert set(tax.c19_names) <= covered
