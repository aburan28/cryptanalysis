# Fixed-size orbit-cover swaps reduce norm-seven work

Replacing selected seeds one for one in the radix-1024 orbit cover reduced
the number of held-out secp256k1 scalars using `rho=1+tau` from **3,112 to
2,346** across 4,096 disjoint inputs. Rho-mapped full-window digits fell
from **5,357 to 3,240**. The native evaluator retained the same
**54,339,936 bytes** and used the same twelve full-window point terms.
Every native point matched the independent control, and the first 128
also matched separate binary multiplication. The complete native Rust
suite passed **143/143 tests**; all ten CLI boundary cases passed.

## Cover construction

The original 67,338-seed cover reaches all 174,764 six-unit residue
classes through the maps `1`, `tau`, `tau^2`, and `rho`. For a selected
seed `S`, let `U(S)` be the classes for which `S` is the only selected
provider. Replacing `S` with a candidate whose four-map orbit contains
`U(S)` preserves complete coverage: every class outside `U(S)` already
has another provider. The deterministic search chooses a replacement
only when it strictly decreases classes lacking any selected tau-map
provider, breaking ties by candidate norm and canonical class index.

Three improving sweeps made 5,897, 389, and 15 swaps; a fourth made
none. The seed count stayed **67,338**, while rho-only classes fell
from **19,001 to 11,396**. Reassigning each class to its best available
tau map, or to rho when required, produced a 1,667,480-byte direct-class
atlas of the same format and size as the control. The independent
[cover verifier](cover-check.json) checked the priority assignment,
all selected seed use, and all **1,048,576 exact residues**. The
[native atlas verifier](native-atlas-check.json) separately checked
every direct-class record and inverse unit action.

## Frozen paired panel

The constructor and holdout tools were committed at `5780cb2452357e1be98945155cbd508deef47bf7`
before the new 4,096-scalar panel was drawn. Its generator seed is
`20261011234517`; [holdout-inputs.json](holdout-inputs.json) records
source hashes and rejects modular collisions with listed earlier
panels. Every path's digit, seed, map, unit, terminal, and scalar
congruence passed the [independent holdout check](holdout-check.json).

| Same-panel format | Scalars using rho | Rho digits | Gauge rotations | Full-window nonzero terms | Retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original fixed priority | 3,112 | 5,357 | 20,438 | 49,152 | 54,339,936 |
| Swapped fixed cover | **2,346** | **3,240** | **19,943** | 49,152 | 54,339,936 |

The swapped cover removed **766 rho activations (24.61%)**, **2,117 rho
digits (39.52%)**, and **495 gauge rotations (2.42%)** on this paired
panel. There were 839 per-scalar activation improvements, 73
regressions, and 3,184 ties. A 5,000-resample paired bootstrap over
the saved paths gives a descriptive 95% interval of **0.174–0.200
fewer rho activations per scalar** around the observed 0.187. The
[analysis receipt](paired-analysis.json) also retains intervals for
rho digits and gauge rotations. The gauge counts come from exact
phase occupancy; the native swapped run reproduced **19,943**.

Using the frozen direct-XYZZ source-call model, 766 fewer nonidentity
rho calls and 495 fewer gauge rotations imply an isolated rho/gauge
subpath delta of `-6,894M -3,830S -2,027C`, where `M` is a general
field multiplication, `S` a squaring, and `C` a fixed-constant Solinas
product. Other evaluator work and CPU lookup costs remain outside this
subpath count. The swapped cover makes one fixed atlas lookup per
window and needs no online beam search.

For a same-panel retrospective diagnostic, the earlier width-two
carry-aware selector on the original cover used rho for 2,906 scalars
and 4,726 digits after examining 114,049 offers. The swapped fixed
cover used rho for 2,346 scalars and 3,240 digits. Its
[comparison receipt](comparison.json) binds both source and input
hashes; that replay did not change either candidate.

## Native correctness and timing boundary

The source-pinned native materializer replaced only the full-window
DR20 atlas in the direct-XYZZ-rho evaluator. Its 4,096-case test checked
every native digit against the frozen path certificate, every point
against the independent control, the first 128 against binary scalar
multiplication, the exact operation counts above, and the unchanged
retained byte count. The [suite receipt](native-check.json) binds the
generated Rust source, atlas, panel, raw test log, and **143 passing
tests**. The [CLI edge receipt](native-edge-check.json) binds the
binary and ten independently verified boundary outputs. Compressed
raw outputs are preserved beside both receipts.

The result establishes a smaller norm-seven stage at unchanged table
size and fixed lookup work. A paired end-to-end wall-time comparison
requires the host-level isolation and noise gates in
`../../docs/ISOLATED_BENCHMARKS.md`; online CPU speedup remains unknown.
