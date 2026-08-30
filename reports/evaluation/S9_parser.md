# S9 — Q1 Rule Parser + M10 Fallback

**Stage:** S9 · **Date:** 2026-08-30 · **STATUS: COMPLETE**

Q1 converts a question string into a typed `QuerySpec`. **No language model** — S3
measured the task space as closed at 15 `type`x`category` combinations over a 19-class
vocabulary, so closed template rules are the correct tool and are auditable in a way a
prompted model is not. Every rule traces to phrasing S3 measured; none was invented.

Fitted on **train**. Reported on **validation**. The quarantined `bench` split was
never touched.

---

## 1. Headline — measured on a HELD-OUT validation slice

| | |
|---|---|
| **Rule coverage** | **99.60%** |
| **Rule precision** (of parsed, intent matches the annotation) | **98.44%** |
| **End-to-end** (parsed AND correct) | **98.04%** |
| Combined with the M10 fallback | 98.44% |
| Unparsed residue | 18 of 4,500 (0.40%) |

> **On the word held-out.** The rules were written by inspecting parse errors, and
> early iterations inspected errors on a *validation* sample — which makes that sample
> development data, not a test set. Every number above comes from a disjoint slice
> (`--holdout-skip 400`) that development never saw. For comparison the contaminated
> development slice scored 99.47 / 98.48 / 97.96, so the difference is within noise
> and the rules generalise. Reporting only the development number would have been
> defensible-looking and wrong.

## 2. Per task

| type | category | n | coverage | precision | end-to-end |
|---|---|---|---|---|---|
| `binary` | `adjacency` | 300 | 100.00% | 93.67% | 93.67% |
| `binary` | `area` | 300 | 97.33% | 95.89% | 93.33% |
| `binary` | `count` | 300 | 100.00% | 100.00% | 100.00% |
| `binary` | `presence` | 300 | 96.67% | 94.83% | 91.67% |
| `bounding box` | `point` | 300 | 100.00% | 100.00% | 100.00% |
| `bounding box` | `reference` | 300 | 100.00% | 100.00% | 100.00% |
| `captioning` | `None` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `adjacency` | 300 | 100.00% | 95.33% | 95.33% |
| `mcq` | `area` | 300 | 100.00% | 96.67% | 96.67% |
| `mcq` | `climate zone` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `count` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `country` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `presence` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `relative pos` | 300 | 100.00% | 100.00% | 100.00% |
| `mcq` | `season` | 300 | 100.00% | 100.00% | 100.00% |

## 3. The HALT condition

The stage prompt halts if rule coverage is low enough that M10 becomes the primary
path rather than a fallback. Coverage **99.60%** against a
50% floor: **PASS** —
the rules are the primary path and M10 is a genuine fallback.

## 4. M10 — fitted, and honestly too small to score

- Training pool: **all 9,000 training questions**, 9 intents.
- Evaluated on the **18** validation questions the rules declined.
- Accuracy on that residue: **100.00%** (18 items).

**That number must not be quoted as an accuracy.** Two reasons, both measured:

1. **n = 18.** The rules are good enough that almost nothing
   reaches the fallback. An interval on 18 items spans most of the unit line.
2. **Duplicate leakage.** S3 measured only ~220k distinct `input` strings across 7.1M
   rows, so questions repeat heavily and train/validation share verbatim text. Of the
   residue, **14 items appear verbatim in training**
   and only **4 are unseen text**. On an earlier run this
   inflated a residue accuracy to a clean 100.00% over 719 items, 38.94% of which were
   verbatim duplicates. Splitting the two is the only honest way to report it.

### Which pool to fit M10 on — measured, not argued

The intuitive choice is to fit M10 only on the questions the rules fail on, since that
is all it ever sees. **Measured, that is wrong here:**

| training pool | distinct labels | accuracy on residue |
|---|---|---|
| rules-residue only (56 items) | 2 | 100.00% |
| **all training questions (9,000)** | **9** | **100.00%** |

The residue holds only 56 items across 2 intents — it cannot span the 9-way label space, so a
residue-fitted M10 is structurally unable to emit most intents. Fitting on all training
questions is what ships.

## 5. Unparsed residue — the honest limitation list

**18 — no intent cue matched**

- `Does the satellite image display mixed forest?`
- `Is the class pastures the only one in the image?`
- `Does the satellite image display natural grasslands or sparsely vegetated areas?`

| task | residue |
|---|---|
| `binary|presence` | 10 |
| `binary|area` | 8 |

**These were deliberately NOT fixed.** They come from the held-out slice; tuning
rules against them would convert the last clean measurement into another development
sample. They are recorded as the limitation list the stage asks for.

## 6. Defects this stage found and fixed

All five were measured on real questions, not hypothesised:

| defect | cost when measured |
|---|---|
| `sea` matched **inside** the word "season" (14 short forms are exposed; `urban` in "suburban", `town` in "downtown") | `mcq|season` precision **0.00%** |
| A class name read as an intent cue — *"Land principally occupied by agriculture, with significant areas..."* contains "occupied" **and** "areas" | 151 presence questions routed to AREA |
| MCQ stems ending in `:` rather than `?` left the option list inside the stem | 68 misroutes |
| `m^2` unmatched — **109 of 333** sampled m² spellings | **drops the stated value** while still routing to AREA: a wrong number, not an abstention |
| Caption stems say "including the region, time of year" | 71 captions routed to METADATA_MCQ |

The `m^2` one is the most serious in kind: the others misroute a question, which is
visible downstream, whereas dropping a stated value produces a confident answer to the
wrong question.

`satquery/routing/parser.py` and `m10_classifier.py` ship with 80 + 19 unit tests, and
each defect above has an assertion that would have caught it.