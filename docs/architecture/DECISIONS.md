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


---

## D-S7-1 — MCQ answers as fitting targets: verified NOT circular

**Decided:** 2026-08-30 (S7) · **Status:** VERIFIED

S7 recovered M2's conventions using the correct MCQ option as ground truth (`mcq|count`'s
option **is** the true region count; `mcq|area`'s range **contains** the true coverage). Because
S3 had already found a real circularity of similar shape (the `country` column equalling its own
MCQ answer 100.00% of the time), this was checked rather than assumed.

**It is not circular, and the argument is information-theoretic rather than rhetorical:**

| | |
|---|---|
| What fitting produced | **5 global scalars** — connectivity, MMU, opening, dilation, boundary rule |
| Capacity of that output | **~7 bits** (14 connectivity x MMU settings, 3 rules, 5 radii) |
| Labels consumed | **1,000**, needing **>= 2,000 bits** to memorise |
| Conclusion | The config **cannot** encode per-patch answers. It selects an algorithm variant. |

At inference M2 receives a *predicted* map plus those scalars and never reads a released answer.

**Contrast with the S5 hazard:** M5's danger was the answer masquerading as an *input* at
inference. Here the answer is used once, offline, to choose an algorithm — then applied to
images whose answers are unseen.

**⚠ The line that must not be crossed at S14:**

- **Permitted:** M4 consumes the four option *values*. They are printed in the question and
  present at inference.
- **LEAKAGE:** M4 consuming the correct-option *letter*, or any feature derived from it, as an
  input feature. That is the M5 error in new clothing. Recorded in CLAUDE.md §7.


---

## D-S7A-1 — The relative-position direction convention

**Decided:** 2026-08-30 (S7 addendum, ordered by the reviewer after the GATE 1 PASS)
**Status:** FITTED, with two components explicitly recorded as UNDER-DETERMINED

S7 fitted connectivity, MMU, opening kernel and adjacency dilation but left the direction rule
uncalibrated. GATE 1 measured `mcq|relative pos` at 65.33% with **0% abstention** — genuinely
wrong answers, not declined ones. The reviewer's reasoning for closing it before S9: Gate 1's
own number was resting on one uncalibrated component while the rest were calibrated, and once
S9's abstention work or S14's MCQ scorer touch this task, any debugging must first rule out
"is this the known unfitted parameter" as a confound. Cheap now, expensive later.

**Result: 65.33% -> 92.67% on validation (+27.34).** At matched n=300, exactly one of nine
tasks moved and the other eight are bit-identical, so the gain is attributable to the
convention and to nothing else.

### The finding that was not what anyone expected

The dominant error was **not** geometric. **25.96% of question stems invert subject and
reference** — `Using the <A> as the reference, ... the position of the <B>` asks for B relative
to A, as do `Relative to the <A>, where does the <B> appear` and `the spatial direction from
<A> to <B>`. Read as written, those score a **forced 0.00%**: exact-matching a reversed bearing
selects the option 180 degrees from the truth whenever offered, and the angular fallback picks
the same, so the reversed reading *cannot* be accidentally right.

**This was fixed in the parser (`oracle.subject_is_second`), not in M2.** Which class is the
subject is a property of the wording; the geometry engine should not know about templates.
`compute_relative_position` documents that its first argument is the subject and stops there.

An anti-drift check in `scripts/fit_direction_convention.py` asserts that what the sweep fits
and what `oracle.subject_is_second` ships agree on every item (2,500/2,500). Without it the
fitted convention and the deployed parser could diverge silently and every reported number
would describe a rule the system does not use.

### What is measured, and what is not

**MEASURED — decisive:** the textbook equal-sector 8-way compass is **wrong**. A 45-degree
diagonal band scores 87.01% against 93.57% for a narrow one. Corroborated by a statistic the
accuracy sweep never optimised for: released answers are cardinal 81.60% of the time while
cardinals are only ~62% of the offered options. Improves in **5/5 folds** (+21.36 to +33.13).

**UNDER-DETERMINED — a non-result, handled exactly as `bin_boundary_rule` was (L-S7-1):**

| | |
|---|---|
| Exact band inside ~[10, 22] deg | **Not resolvable.** McNemar exact tests over 2,500 items separate no candidate from any other; best p = 0.068 |
| `mask_centroid` vs `largest_component` | Differ in *position* on 263/2,500 items and change **zero** predicted answers |
| `mask_centroid` vs `bbox_centre` | Change 40/2,500 answers; 0.39 pts apart; p = 0.072 |

The shipped values are **not** the accuracy argmax. `diagonal_band_deg = 16` is the one value
where two *independent* lines of evidence converge: it lies inside the accuracy plateau **and**
it reproduces the observed diagonal-answer rate. `direction_reference_rule = mask_centroid` is
adopted on two non-accuracy grounds — it is the same "a class **is** its mask" semantics that
`compute_area` and `compute_count` already use, and the centre of a *union* bounding box is
maximally sensitive to a single stray pixel, which is precisely the wrong statistic once S13
feeds M2 predicted maps instead of ground truth. **No result may be attributed to 16 over 14,
or to `mask_centroid` over `largest_component`.**

The selection rule is encoded in the fitting script rather than applied by hand: prefer the
convergent candidate unless McNemar can actually separate it from the argmax at p < 0.05.

### Capacity check (D-S7-1's argument, reapplied)

Fitted here: 4 booleans + a 3-way choice + one scalar, well under 10 bits, against 2,500
supervised labels needing >= 5,000 bits to memorise. A convention of this size cannot encode
per-patch answers. Train only; evaluated on validation.

### Residual — I guessed, then measured, and the measurement contradicted me

I wrote into the draft report that the remaining error was most likely the `between` family's
symmetric phrasing. **Measuring it proved that wrong:** `between` is at 95.97%, the second-best
family. All four land within 93.74%-97.10% and each family's share of the residual tracks its
share of the items. Orientation is fully resolved; what remains is evenly-distributed
borderline-angle error, which is what an under-determined band width predicts. The claim was
removed from the report and replaced with the measured table. Another instance of CLAUDE.md §5.
