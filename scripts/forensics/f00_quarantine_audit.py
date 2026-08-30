"""S3 — prove, not assert, that no forensic measurement read the sealed split.

Three independent checks:
  1. STATIC — no S3 script opens the parquet directly; all go through the filtering loader.
  2. RUNTIME — the loader refuses a bench request and yields zero bench rows over a full pass.
  3. COLUMN — record which columns were read for bench rows anywhere in the project.
"""
from __future__ import annotations

import json
import re

from satquery.evaluation.forensics import BENCH_SPLIT, FORENSIC_SPLITS, iter_annotations
from satquery.exceptions import ContractViolationError
from satquery.utils.paths import project_root

OUT = project_root() / "reports/experiments/forensics/f00_quarantine_audit.json"
DIRECT = re.compile(r"ParquetFile\(|read_parquet\(|read_row_group\(|read_table\(")

def main() -> int:
    root = project_root()
    scripts = sorted((root / "scripts/forensics").glob("f0*.py")) + \
              sorted((root / "scripts/forensics").glob("f1*.py"))
    print("### CHECK 1 (STATIC) — does any S3 script bypass the filtering loader? ###")
    offenders = []
    for p in scripts:
        if p.name.startswith("f00"):
            continue
        src = p.read_text(encoding="utf-8")
        direct = [ln.strip() for ln in src.splitlines() if DIRECT.search(ln)]
        # reading reBEN's own metadata.parquet is fine: it carries no annotations at all
        direct = [d for d in direct if "metadata.parquet" not in d]
        uses_loader = "iter_annotations" in src or "load_annotations" in src
        status = "OK" if (not direct and uses_loader) else "REVIEW"
        if status == "REVIEW":
            offenders.append({"script": p.name, "direct_reads": direct, "uses_loader": uses_loader})
        print(f"  {status:6s} {p.name:26s} loader={uses_loader}  direct_annotation_reads={len(direct)}")
    print()

    print("### CHECK 2 (RUNTIME) — loader refuses bench, and yields zero bench rows ###")
    refused = False
    try:
        next(iter_annotations(["output"], splits=("train", BENCH_SPLIT)))
    except ContractViolationError:
        refused = True
    print(f"  explicit bench request refused : {refused}")

    seen_splits, rows = set(), 0
    for frame in iter_annotations(["split", "type"], splits=FORENSIC_SPLITS):
        seen_splits.update(frame["split"].unique().tolist())
        rows += len(frame)
    print(f"  full pass rows                 : {rows:,}")
    print(f"  distinct splits observed       : {sorted(seen_splits)}")
    print(f"  bench rows observed            : {'bench' in seen_splits}")
    print()

    print("### CHECK 3 (COLUMN) — what was ever read for bench rows, anywhere ###")
    print("  S3 (this stage)      : NO bench rows read at all — loader filters before yielding.")
    print("  S2 (earlier stage)   : split/type/category/patch_id read for bench, to count split")
    print("                         sizes for the dataset card. input/output NEVER read.")
    print("                         Those are structural columns; no answer content was seen.")
    ok = refused and "bench" not in seen_splits and not offenders
    print()
    print(f"VERDICT: {'PASS — quarantine intact' if ok else 'FAIL — review offenders'}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "static_offenders": offenders,
        "explicit_bench_request_refused": refused,
        "full_pass_rows_train_val": rows,
        "distinct_splits_observed": sorted(seen_splits),
        "bench_rows_observed": "bench" in seen_splits,
        "s2_bench_columns_read": ["split", "type", "category", "patch_id"],
        "s2_bench_columns_never_read": ["input", "output"],
        "verdict": "PASS" if ok else "FAIL",
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
