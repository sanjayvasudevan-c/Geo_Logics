# Dataset Card — reBEN reference maps, local development store

Required by CLAUDE.md §7 and STAGE_PROMPTS.md S2 item 5.
Created: 2026-08-30 (Stage S2). Seed: **1337**.

> **This store is for S3–S8 development only. All headline results come from the full split,
> never from this store.**

---

## 1. What this is

The complete set of **CORINE Level-3 pixel reference maps** from reBEN / BigEarthNet v2.0,
extracted locally. It is M1's supervision target and, more immediately, the input to the **S8
oracle experiment (GATE 1)**, which feeds *ground-truth* maps into M2 rather than predictions.

It contains **no imagery**. See §6.

| | |
|---|---|
| Source | Zenodo record [10891137](https://zenodo.org/records/10891137), `Reference_Maps.tar.zst` |
| Licence | **CDLA-Permissive-1.0** (verified — see `LICENCE_AUDIT.md`) |
| Archive size | 282,391,301 B (md5 `95d85a22…`, verified on download) |
| Extracted count | **549,488 maps** |
| Logical size | 533,265,639 B (**533 MB**) |
| Format | Single-band GeoTIFF, 120 × 120, `uint16`, nodata `0` |
| CRS | UTM, EPSG:326xx (zones 29–35 observed) |
| Layout | `data/interim/reben/reference_maps/<S2_tile_id>/<patch_id>.tif` |
| Shards | 54 tiles — min 261, median 7,263, max 32,831 maps |

---

## 2. Selection method — and why there is no subset

**Selection: exhaustive. Every map in the archive, no sampling.** Seed 1337 is recorded for
provenance and for downstream stratified splits built from this store, but no RNG was used: the
selection is total.

The S2 plan called for a stratified geographic subset sized to available disk. Two measurements
made that unnecessary, and then actively undesirable:

1. **Cost.** Measured 970.5 B logical per map. Even at full size the store is 533 MB logical,
   comfortably inside budget. A subset saved little.
2. **Rare-class starvation.** A probe over 30,000 patches found **44 distinct CLC L3 classes**,
   but **6 of them appear in under 0.1% of patches** — rarest, class `521` (coastal lagoons), in
   **3 of 30,000**. Scaled to a ~20,000-patch subset that class would land at roughly **2
   patches**, which cannot support a per-class oracle measurement. Taking 100% removes the
   starvation risk entirely rather than trading it off.

Classes appearing in <0.1% of the probe: `123`, `332`, `334`, `422`, `423`, `521`.

> **Caveat on the probe:** it read the *first* 30,000 members in archive order, which is tile-
> ordered and therefore **geographically biased**. The class list should be treated as a floor
> on diversity, not a complete inventory — the full store is exhaustive regardless, so this
> caveat does not affect the store itself. Re-derive class statistics from the full store at S4.

---

## 3. Corrected storage reference figures

**For anyone re-projecting storage for the full run (S12), use these, not the earlier estimates.**

| Figure | Value | Notes |
|---|---|---|
| Logical bytes per map | **970.5 B** | Exact, from the extraction manifest |
| **Allocated bytes per map** | **~4,621 B** | Measured on the final 139,488-map pass |
| Slack factor | **~4.76×** | Small files on NTFS; many are near or below one 4 KiB cluster |
| Total store, logical | 533 MB | |
| **Total store, on disk** | **~2.54 GB** | 549,488 × ~4,621 B |

**A flat-directory probe measured only 3,670 B/map and under-projected the store by ~25%.** The
sharded layout adds per-directory metadata and MFT growth that a flat probe does not capture.
Use ~4,621 B/map, or measure in the target layout — not a flat one.

The extraction manifest previously divided a *resumed* run's free-space delta by the *total*
count, which under-reports per-map cost. Fixed: the fields are now
`allocated_bytes_this_run`, `bytes_per_map_allocated_this_run` and
`estimated_total_allocated_bytes`.

---

## 4. Count discrepancies — both resolved, neither a contradiction

Three different patch counts are in play. They are all correct and describe different products.

| Count | What it is |
|---|---|
| **549,488** | All reBEN patches — and **the number of reference maps in this archive** |
| 480,038 | reBEN patches surviving snow/cloud/shadow screening (`metadata.parquet`) |
| 464,044 | Patches that BigEarthNet.txt actually annotated |

- 480,038 + 69,450 (snow/cloud parquet) = **549,488** exactly.
- 464,044 is a **clean subset** of 480,038: verified **0** patches exist in BigEarthNet.txt that
  are absent from reBEN; 15,994 reBEN patches carry no annotation.
- **This archive is exhaustive**, holding a map for every patch including the 69,450 screened
  out. Planning against `metadata.parquet`'s 480,038 under-counts the extraction by 14.5% —
  which is exactly what happened here, and is why §3's figures are stated against 549,488.

No architecture figure is contradicted. No Gate Report was warranted.

---

## 5. Integrity verification

| Check | Result |
|---|---|
| Archive md5 | **Verified** against Zenodo manifest before extraction |
| Corrupt-file scan | **300 sampled at seed 1337, 0 corrupt** |
| Readable by `rasterio` | **Yes** — CLAUDE.md §1 forbids PIL/OpenCV/`imread` for GeoTIFFs |
| Shape | All `(120, 120)` |
| Dtype | All `uint16` |
| Band count | All `1` (reference map is single-band by design) |
| Patch ids without a parsable tile | **0** |
| Shards | 54, matching the 54 distinct S2 tiles in `metadata.parquet` |

---

## 6. What is deliberately absent — and the S12 warning

**No imagery.** The Sentinel-1 and Sentinel-2 archives total **117.69 GB** and are not fetched
locally; `fetch_reben.py` refuses them as `tier: deferred`. They are first required at S11/S12,
covered by the standing cloud GPU+disk decision in `PROJECT_STATUS.md`.

> **Warning for S12 planning — plan for a full-archive download, not a selective one.**
> Zenodo serves `BigEarthNet-S1.tar.zst` (54.44 GB) and `BigEarthNet-S2.tar.zst` (63.25 GB) as
> **monolithic archives with no per-patch HTTP access**. A stratified subset of the *imagery*
> therefore cannot be selectively downloaded — obtaining any subset requires pulling the whole
> 117.69 GB first. Every Hugging Face mirror probed returned **HTTP 401 unauthenticated**, so no
> shard-accessible alternative was confirmed. Unless an `HF_TOKEN` later demonstrates shard
> access, budget for the full 117.69 GB transfer plus extraction space.
>
> Reference maps do not share this constraint: `tar` supports selective extraction over a
> streamed zstd archive, which is how this store was built and resumed.

---

## 7. Known limitations

- **Development store, not a result store.** Fine for S3–S8. Every headline number must come
  from the full split (CLAUDE.md §7 and the standing decision).
- **Reference maps are not imagery.** Anything requiring pixels — M1 training, TTA, the transfer
  factor at S13 — is blocked until the imagery decision at S12.
- **CORINE label noise is irreducible.** Polygons were photo-interpreted at 1:100,000 with a
  25 ha minimum mapping unit, then rasterised to 10 m, so labels disagree with pixels near every
  boundary. This bounds oracle accuracy from above and is a property of the data, not our method.
- **15,994 maps have no annotation** and are inert for S8 scoring. They are retained because
  discarding them would complicate reproducing the extraction.
- **The class-frequency probe is geographically biased** (§2 caveat). Re-derive at S4.

---

## 8. Reproduction

```bash
uv run python scripts/data/fetch_reben.py              # 287 MB, md5-verified, idempotent
uv run python scripts/data/extract_reference_maps.py   # ~549k maps, resumable
```

Both are idempotent: re-running the fetch performs no network I/O (1.7 s), and the extraction
skips maps already on disk at ~1,900/s versus ~400/s writing.

Manifest: `data/interim/reben/reference_maps_manifest.json`
Config: `configs/datasets/reben.yaml` (sizes and digests as config, per CLAUDE.md §8)

**Note on long runs:** extraction takes longer than this machine's 10-minute idle-sleep
threshold and was killed twice before completing. `satquery.utils.keepawake` now holds a
process-scoped power request for the duration. See `PROJECT_STATUS.md` for the verification
status of that mechanism.
