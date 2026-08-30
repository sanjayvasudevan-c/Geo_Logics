# Split Quality Report — S6 Geographic Block CV

**Date:** 2026-08-30 · **Seed:** 1337 · **k = 5** · **Population:** reBEN `train`, 237,871 patches

**STATUS: HALTED.** Rare CLC classes cannot be covered across all folds under geographic
blocking. See §5 and `GATE_REPORT_S6.md`.

---

## 1. The headline: what a random split would have cost

Two independent measurements, both on real data, both pointing the same way.

### 1a. Physically touching patches severed by the split

Adjacency is **exact, not inferred**: reBEN patch ids encode `tile`, `row`, `col`, so two
patches in the same tile differing by at most one in each are touching. No rounding.

| Split | Adjacent pairs split across folds | of 419,356 total |
|---|---|---|
| **Random** | **335,195** | **79.93%** |
| `s2_tile` (geographic) | **0** | **0.00%** |

**A random split severs four out of every five physically touching patch pairs**, placing
near-identical neighbours on opposite sides of the train/validation boundary.

### 1b. Repeat acquisitions of the same ground location

reBEN images the same ground location on multiple dates. This was **not** anticipated by the
architecture and is the larger hazard of the two.

| Measurement | Value |
|---|---|
| Distinct ground locations `(tile, row, col)` | 115,040 |
| Locations with repeat acquisitions | **69,479** |
| Patches involved | **192,310 — 80.8% of the training split** |
| Max acquisitions of one location | 4 |
| **Random split** — locations whose twins land in different folds | **62,195 (89.5%)** |
| **`s2_tile`** — locations whose twins land in different folds | **0 (0.0%)** |

Under a random split, **89.5% of repeat-imaged locations put a near-twin of a training patch
into validation.** That is near-duplicate leakage of the most direct kind: the same ground, a
few months apart.

### 1c. Same-block rate among cross-fold pairs

| Blocking | Random split | Geographic split |
|---|---|---|
| `country` | 18.617% | **0.000%** |
| `grid_1deg` | 1.910% | **0.000%** |
| `s2_tile` | 3.321% | **0.000%** |

---

## 2. Strategy comparison — and why the label check is not enough

Every strategy passes the **LABEL** check (no block spans folds). Only one passes the
**BINDING** check (no physically touching pair spans folds).

| Strategy | Blocks | Fold balance | LABEL: blocks spanning | **BINDING: touching pairs split** | Min inter-fold distance |
|---|---|---|---|---|---|
| `country` | 10 | 0.498 | 0 | **47 (0.0112%)** | 10.880 km |
| `grid_1deg` | 123 | 1.000 | 0 | **8,769 (2.2095%)** | 0.419 km |
| **`s2_tile`** | 54 | 0.991 | 0 | **0 (0.0000%)** | 0.359 km |

- **`grid_1deg`** has the best fold balance and looks perfect by the label check, yet splits
  **8,769 touching pairs**. Patches straddling a 1-degree cell boundary are physically adjacent
  across two blocks. This is the edge-of-cell hazard, and no amount of checking block labels
  would have revealed it.
- **`country`** splits 47 pairs, where a national border runs through a tile. Its fold balance
  is also poor (0.498) because Finland alone is 74,293 patches.
- **`s2_tile`** splits zero and balances to 0.991.

**RECOMMENDED: `s2_tile`.** It matches the data's own organisation, contains within-tile
adjacency by construction, contains all repeat acquisitions, and balances well.

### Residual limitation, stated because it bounds the claim

Within-tile grid adjacency cannot see across tile boundaries. `s2_tile`'s minimum inter-fold
great-circle distance is **0.359 km**, below the 1.2 km patch width — so patches in *different*
tiles do sit close to each other across the fold boundary. Sentinel-2 tiles overlap, so this is
expected. `s2_tile` eliminates within-tile leakage entirely and reduces but does not eliminate
cross-tile proximity. Quantifying the residual needs an exhaustive geographic pass, not a
sample; deferred with the number above recorded as a sampled lower bound.

---

## 3. Fold composition (`s2_tile`, k=5, seed 1337)

| Fold | Patches |
|---|---|
| 0 | 47,492 |
| 1 | 47,800 |
| 2 | 47,601 |
| 3 | 47,383 |
| 4 | 47,595 |

Balance (min/max) = **0.991**. 54 tiles across 5 folds.

### Countries per fold

| Country | f0 | f1 | f2 | f3 | f4 |
|---|---|---|---|---|---|
| Austria | 1,290 | 4,971 | 5,232 | 8,778 | 4,701 |
| Belgium | 0 | 0 | 2,699 | 0 | 5,138 |
| Finland | 7,630 | 14,674 | 556 | 26,778 | 24,655 |
| Ireland | 5,718 | 696 | 14,401 | 0 | 1,667 |
| **Kosovo** | 0 | 0 | **849** | 0 | 0 |
| Lithuania | 10,093 | 3,249 | 9,828 | 0 | 0 |
| **Luxembourg** | 0 | 0 | **1,888** | 0 | 0 |
| **Portugal** | 16,030 | 15,864 | **0** | 11,827 | **0** |
| Serbia | 5,039 | 8,346 | 12,148 | 0 | 11,434 |
| **Switzerland** | **1,692** | 0 | 0 | 0 | 0 |

**Three countries occupy a single fold each** (Kosovo → f2, Luxembourg → f2, Switzerland → f0),
and **Portugal is absent from folds 2 and 4**. This is the mechanism behind §5.

---

## 4. Split artifacts

Splits are an artifact, not a recomputation (CLAUDE.md §8):

```
data/processed/splits/country_k5_seed1337.json
data/processed/splits/grid_1deg_k5_seed1337.json
data/processed/splits/s2_tile_k5_seed1337.json
```

Each records strategy, k, seed, block count, fold sizes, and the full patch→fold and
patch→block maps.

---

## 5. ⛔ HALT — rare classes are not covered in every fold

**S6's stated halt condition is met.** Sampling 900 maps per fold (seed 1337), **20 of the 44
CORINE L3 classes are absent from at least one fold**:

```
123 124 131 132 133 141 212 213 223 241 244 323 331 332 333 334 335 422 521 522
```

**This is structural, not a sampling artifact**, and the country table in §3 shows why. Every
Mediterranean class absent from folds 2 and 4 is Portugal-concentrated, and **Portugal has no
patches in folds 2 or 4**:

| Code | Class | f0 | f1 | f2 | f3 | f4 |
|---|---|---|---|---|---|---|
| 212 | Permanently irrigated land | 41 | 41 | **0** | 8 | **0** |
| 213 | Rice fields | 16 | 7 | **0** | 4 | **0** |
| 223 | Olive groves | 55 | 43 | **0** | 16 | **0** |
| 241 | Annual crops w/ permanent crops | 26 | 14 | **0** | 8 | **0** |
| 244 | Agro-forestry areas | 112 | 116 | **0** | 59 | **0** |
| 323 | Sclerophyllous vegetation | 19 | 4 | **0** | 41 | **0** |
| 522 | Estuaries | 5 | 11 | **0** | **0** | **0** |

Code **335 (Glaciers and perpetual snow) is absent from every fold** — consistent with S4,
which found it absent from the corpus entirely.

The remaining absences (123 Port areas, 132 Dump sites, 334 Burnt areas…) have single-digit
counts and may be sampling artifacts; distinguishing them needs an exhaustive per-fold scan.

**Why this is inherent, not a bug:** geographic blocking prevents leakage *precisely by
separating regions*. A class confined to one region therefore cannot appear in every fold. The
two goals are in direct tension, and no fold assignment resolves it while blocks stay intact.

**Consequence if unresolved:** per-fold per-class IoU is undefined for absent classes, so a
mean-over-folds mIoU is computed over a different class set per fold and is not comparable.
This bears directly on GATE 2's transfer factor.

Decision required — see **`reports/experiments/GATE_REPORT_S6.md`**.
