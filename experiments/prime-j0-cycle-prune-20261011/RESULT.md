# Fixed-memory tau-cycle cover reduces norm-seven work

Cycle pruning and exchanges produce a **67,338-seed** radix-1024 cover with
**6,226 rho-only classes**, versus **11,396** for the preceding cover at the
same seed count. The exact tau-only lower bound at this budget is **6,079**;
the construction is **147 classes** above it. Every class assignment and all
**1,048,576 residues** passed independent verification.

## Construction and exact coverage

The [pruner](prune.py) starts from the exact 73,417-seed tau-only cover and
deletes 4,674 seeds while preserving coverage by `1`, `tau`, `tau^2`, and
`rho=1+tau`. It stops at 68,743 seeds and 4,841 rho-only classes. The
[exchange search](exchange.py) scans 5,468 feasible two-for-one replacements
and accepts 1,405, checking all affected class counts after each change.
This reaches the 67,338-seed budget with 6,262 rho-only classes. A final
[one-for-one pass](refine.py) improves 36 assignments and reaches 6,226.
The [independent exchange replay](exchange-check.json) verifies every
replacement; the [cover receipt](cover-check.json) checks all three tables,
all seed use, priority assignments, and every residue.

For a `k`-seed cover with `U` classes lacking a tau provider, a direct seed
for each such class completes a tau-only cover. The parent exact minimum
therefore gives `U >= 73,417 - k = 6,079` at `k=67,338`. This bound is for
the stated radix, norm limit, and one-seed-per-class representation.

## Frozen paired scalar panel

The construction and panel tools were frozen in commit
`7be47af838acb92fd7f2c615bb528eb683963ecd` before drawing the new
4,096-scalar panel with seed `20261011090617`. The [input receipt](holdout-inputs.json)
records source and cover hashes and checks modular disjointness against the
listed prior panels. The [path verifier](holdout-check.json) replayed each
digit, seed, map, unit, terminal, and scalar congruence; 128 independently
computed binary point fixtures also passed.

| Same 4,096-scalar panel | Seeds | Scalars using rho | Rho digits | Gauge rotations | Full-window nonzero terms | DR20 atlas bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Swapped fixed cover | 67,338 | 2,249 | 3,152 | 19,948 | 49,152 | 1,667,480 |
| Cycle-refined cover | **67,338** | **1,442** | **1,741** | **19,535** | 49,152 | **1,667,480** |

The refined cover saves **807 rho activations (35.88%)**, **1,411 rho
digits (44.77%)**, and **413 grouped-unit rotations (2.07%)** on paired
inputs. There are 1,162 per-scalar activation improvements, 355 regressions,
and 2,579 ties. A 5,000-resample paired bootstrap over saved paths gives a
descriptive 95% interval of **0.179–0.215 fewer activations per scalar**;
the [analysis receipt](paired-analysis.json) contains intervals for digits
and rotations. The [native atlas verifier](native-atlas-check.json) checks
every DR20 class record and its inverse-unit action for all residues.

With the frozen direct-XYZZ source-call model, 807 fewer rho calls and 413
fewer gauge rotations change the rho/gauge subpath by **`-7,263M -4,035S
-2,027C`**: each rho call contributes `9M+5S+2C`, and each gauge rotation
contributes `C`. `M` denotes a general field multiplication, `S` a squaring,
and `C` a fixed-constant Solinas product. The complete evaluator also incurs
table access and other point arithmetic.

## Native point replay and timing boundary

The [materializer](materialize_native.py) binds the refined DR20 atlas and
frozen paths to the direct-XYZZ Rust evaluator. Its 4,096-case point test
passed on the local ARM64 Mac, including comparison with the adic path,
certified digits, and 128 independently computed binary points. The
[source-bound receipt](native-targeted-check.json) retains the complete raw
test log, generated source and asset hashes, test binary hash, and the
terminal `1 passed; 0 failed` result. Its 2,445.13-second elapsed time is a
correctness-run observation on a contended host. The focused Linux workflow
for the complete native suite and CLI edge fixtures is queued. CPU wall-time
ratios require the host-level isolation receipt specified in
`../../docs/ISOLATED_BENCHMARKS.md`.
