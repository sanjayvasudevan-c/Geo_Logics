# Licence Audit

Required by STAGE_PROMPTS.md S2 item 4. Per CLAUDE.md §5, an entry is marked **VERIFIED** only
where the licence was read from the distributor's own metadata during this session. Anything
else is **NOT YET VERIFIED** and must be closed before submission.

Last updated: 2026-08-30 (Stage S2).

---

## Summary

| Dataset | Licence | Verified? | Redistribute? | Hackathon demo? | Blocks anything? |
|---|---|---|---|---|---|
| reBEN / BigEarthNet v2.0 | CDLA-Permissive-1.0 | **VERIFIED** | Yes, with attribution | Yes | No |
| BigEarthNet.txt | CDLA-Permissive-1.0 | **VERIFIED** | Yes, with attribution | Yes | No |
| SECOND | — | **NOT YET VERIFIED** | — | — | Unknown — S17 |
| CDVQA | — | **NOT YET VERIFIED** | — | — | Unknown — S17 |
| VRSBench | — | **NOT YET VERIFIED** | — | — | Unknown |
| RSVQA | — | **NOT YET VERIFIED** | — | — | Unknown |
| ESA WorldCover 10 m v200 | CC-BY-4.0 (per architecture) | **NOT YET VERIFIED** | — | — | Unknown — S23 |
| Google Dynamic World V1 | CC-BY-4.0 (per architecture) | **NOT YET VERIFIED** | — | — | Unknown — S23 |
| Bhuvan LULC (NRSC/ISRO) | — | **NOT YET VERIFIED** | — | — | Unknown — S23 |
| InternVL3-1B | MIT (per architecture) | **NOT YET VERIFIED** | — | — | Unknown — S19 |

---

## VERIFIED entries

### reBEN / BigEarthNet v2.0

- **Source:** Zenodo record [10891137](https://zenodo.org/records/10891137)
- **Licence:** `cdla-permissive-1.0` — read directly from the Zenodo API `metadata.license.id`
  field on 2026-08-30.
- **Full name:** Community Data License Agreement – Permissive, Version 1.0.
- **Redistribution:** Permitted. CDLA-Permissive-1.0 allows use, modification and redistribution
  of the data and of derived results, including commercially.
- **Obligations:** Retain the licence notice and attribution with any redistributed *data*. The
  licence explicitly does **not** impose conditions on "Results" — the outputs of computational
  analysis — so trained model weights and reported metrics carry no downstream obligation.
- **Hackathon demonstration:** Permitted. No non-commercial or research-only restriction.
- **Blocks anything?** No.
- **Attribution text to carry:**
  > BigEarthNet v2.0 (reBEN), TU Berlin / BIFOLD. Licensed under CDLA-Permissive-1.0.

### BigEarthNet.txt

- **Source:** Hugging Face
  [`BIFOLD-BigEarthNetv2-0/BigEarthNet.txt`](https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt),
  pinned to revision `72d865f2146f0a85b720f7f3ca1cdbaeafc3d316`.
- **Licence:** `cdla-permissive-1.0` — read from the repository card metadata and corroborated
  by txt.bigearth.net, which states "Community Data License Agreement - Permissive, Version 1.0".
- **Gated:** No. No token or terms acceptance required; verified by an unauthenticated fetch.
- **Redistribution / demonstration:** As reBEN above.
- **Blocks anything?** No.
- **Note:** This file contains the quarantined benchmark split (1,082 pairs / 15,029
  annotations). The restriction on that split is *ours*, from CLAUDE.md §7 — it is a
  methodological quarantine, not a licence term.

---

## NOT YET VERIFIED

These must be closed before submission. Each is scheduled for the stage that first needs it.

| Dataset | Why it matters | Close by |
|---|---|---|
| **SECOND** | M6's supervision. The architecture notes it is distributed via the CDVQA authors rather than an official portal, so the licence chain needs checking, not assuming. | S17 |
| **CDVQA** | The change-path scoring benchmark. Derived from SECOND, so its licence may inherit constraints. | S17 |
| **VRSBench** | Mandated evaluation, and the only sub-metre imagery we can legally obtain. If restricted, the scale-robustness argument needs rewording. | Before first use |
| **RSVQA** | Mandated evaluation only. | Before first use |
| **ESA WorldCover 10 m v200** | Primary Indian weak labels. Architecture states CC-BY-4.0; unverified here. | S23 |
| **Google Dynamic World V1** | Indian weak labels with confidence. Architecture states CC-BY-4.0; unverified here. | S23 |
| **Bhuvan LULC (NRSC/ISRO)** | Presented to ISRO judges as their own product. A licence or usage claim made on stage must be right. Also open question #10 in IMPLEMENTATION_MAP §10.1: whether Bhoonidhi ≥5 m data is genuinely open to a non-government entity. | S23 |
| **InternVL3-1B** | M7's backbone. Architecture states MIT with a Qwen2.5-0.5B (Apache-2.0) base. Model weights carry their own terms distinct from the dataset. | S19 |

---

## Open licence questions carried from the architecture

From IMPLEMENTATION_MAP §10.1 (REV Appendix B):

- **#8** — Licence status of SECOND, CDVQA, VRSBench and the reBEN pretrained checkpoints.
  "Are your training data legally usable?" should get a table, not a hesitation. This document
  is that table; it is half-complete.
- **#9** — Were the reBEN pretrained checkpoints trained on train only, or train+val+test? Not a
  licence question, but it is a *usability* question resolved from the same model cards. If
  train+val+test, using them leaks into our evaluation.
- **#10** — Is Bhoonidhi data at ≥5 m genuinely open for a non-government entity under current
  policy? Verify directly; do not repeat a second-hand claim.

## Attribution block for the submission

Currently sufficient for what has been acquired:

> This work uses BigEarthNet v2.0 (reBEN) and BigEarthNet.txt, produced by TU Berlin / BIFOLD,
> both licensed under the Community Data License Agreement – Permissive, Version 1.0.

To be extended as each NOT YET VERIFIED dataset is acquired and its terms confirmed.
