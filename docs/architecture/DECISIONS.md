# Decisions and Disclosed Limitations

Durable record of decisions taken and limitations accepted, carried forward to the final
evaluation (S24) and the judge pack (S26). A limitation recorded here is **disclosed, not
hidden** — the reasoning is written out so it can be defended rather than discovered.

---

## D-S6-1 — Split strategy: `s2_tile` with stratified block-to-fold allocation

**Decided:** 2026-08-30 (S6) · **Status:** FINAL
**Artifact:** `data/processed/splits/FINAL_s2_tile_stratified_k5_seed1337.json`

Blocking by Sentinel-2 tile, k=5, seed 1337, with rarity-aware stratified allocation of whole
tiles to folds.

**Why `s2_tile`.** All three candidate strategies pass the label check (no block spans folds).
Only `s2_tile` passes the binding check:

| Strategy | blocks spanning folds | physically touching pairs split | fold balance |
|---|---|---|---|
| `country` | 0 | 47 (0.0112%) | 0.498 |
| `grid_1deg` | 0 | **8,769 (2.2095%)** | 1.000 |
| `s2_tile` | 0 | **0 (0.0000%)** | 0.991 |

`grid_1deg` had the *best* fold balance while silently severing 8,769 physically adjacent
patch pairs at 1-degree cell boundaries. Fold balance was treated as a property of the chosen
strategy, never as a selection criterion.

**Why stratified allocation.** Block *integrity* and block *assignment* are independent.
Size-balanced packing left 3 classes absent from a fold purely as an artifact of packing order.
Rarity-aware allocation removes all 3 at a cost of 0.991 → 0.954 fold balance, with the leakage
guarantee unchanged (0 touching pairs split either way).

---

## L-S6-1 — Cross-tile adjacency is reduced, not eliminated  ⚠ DISCLOSED LIMITATION

**Status:** ACCEPTED AND DISCLOSED. Not to be chased further.

Within-tile adjacency is testable exactly, because reBEN patch ids encode `tile`, `row`, `col`.
Patches touching **across** a tile boundary carry different tile ids and are invisible to that
test.

Measured: `s2_tile`'s minimum inter-fold great-circle distance is **0.359 km**, below the
1.2 km patch width. Sentinel-2 tiles overlap, so cross-tile proximity across a fold boundary is
expected and real.

**Honest framing for the judge pack:** *`s2_tile` blocking eliminates within-tile leakage
entirely — zero of 419,356 touching pairs are split — and reduces but does not eliminate
cross-tile leakage. The 0.359 km figure is a sampled lower bound, not an exhaustive
measurement.*

This is a disclosed limitation, not a gap to hide. Quantifying the residual exactly would need
an exhaustive geographic pass over all 237,871 patches; deferred deliberately.

---

## L-S6-2 — 14 CORINE classes cannot reach every fold  ⚠ IRREDUCIBLE, PROVEN

**Status:** IRREDUCIBLE. Verified, not assumed.

Blocks are atomic, so **a class present in fewer than k=5 tiles cannot appear in all 5 folds
under any allocation whatsoever.** Fourteen classes are in that position:

```
123 Port areas            124 Airports                 212 Permanently irrigated land
213 Rice fields           223 Olive groves             241 Annual crops w/ permanent crops
244 Agro-forestry areas   323 Sclerophyllous veg.      334 Burnt areas
335 Glaciers (0 tiles)    422 Salines                  423 Intertidal flats
521 Coastal lagoons       522 Estuaries
```

Stratified allocation reaches exactly this floor: **14 absent, 0 of them removable.** The
absence was therefore *checked* rather than assumed, which is what makes it defensible.

Most are single-growing-region Mediterranean crops concentrated in Portugal. 335 Glaciers is
absent from the corpus entirely (S4 found 43 CORINE codes + 999, not 44).

**Measurement caveat:** per-tile class presence was sampled at 140 maps per tile, which
undercounts tiles containing very rare classes. The irreducible set is therefore an **upper
bound** — an exhaustive scan could move a class from irreducible to reducible, never the
reverse. The asymmetry means the current reporting is conservative in the safe direction.

> **QUEUED VERIFICATION — V-S6-1. Low priority, non-blocking, must not silently persist.**
> Run an **exhaustive** per-tile class scan (all 237,871 training maps, not 140/tile) to tighten
> 14 to its true value. Cost is ~20-40 min of pure CPU with no GPU and no network, so the
> natural moment is while the **S12 GPU rental is idle or warming up**. Command:
> `uv run python scripts/data/tile_class_presence.py --exhaustive`
> **Deadline: before S24 locks the final judge-facing numbers.** If it has not been run by
> then, S24 must state explicitly that 14 is a sampled upper bound rather than presenting it
> as exact. Do not let this reach S26 unexamined.

**Reporting discipline this forces — binding on S13, S24, S26:**

1. Per-class IoU is reported **only over folds containing that class**.
2. Per-class fold coverage is published **beside every number**.
3. Mean-over-folds mIoU is **not comparable across classes** with different fold-presence sets,
   and must never be presented as if it were.

---

## D-S6-2 — k=5 unchanged, and no collapse to coarse-7

Two workarounds were considered and **rejected**, because both would be quiet architecture
changes disguised as fixes:

- **Reducing k** would improve coverage but contradicts CLAUDE.md §1, which freezes k=5. It
  would require a §6 change request, and it does not help single-tile classes anyway.
- **Reporting cross-fold results at coarse-7** would make coverage complete, but hides exactly
  the sibling-level confusion the benchmark's adversarial "no" answers are built from
  (IMPLEMENTATION_MAP §1.4). The reported level would no longer match the segmentation target.
