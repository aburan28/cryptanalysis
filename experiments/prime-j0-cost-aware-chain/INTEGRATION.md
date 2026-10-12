# Prepared cost-aware τ scalar multiplication: C integration

This branch is stacked on PR #250. It imports the existing local prime-field
`j=0` τ implementation whose pre-import `src/ec_tau.c` SHA-256 is
`128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`.
The import is scoped to scalar arithmetic: no rho walk or dispatch is changed.
It adds an opt-in prepared evaluator that searches the same 25 representatives
as the baseline, scores each exact width-4 schedule with the frozen
`10 triple + 16 mixed add + 1 nontrivial unit rotation` model, and evaluates
the selected digits with the same precomputed points and tripling formula.
The selected digits are reused directly; there is no 26th recoding.

## Correctness result

The C curve test compares ordinary `ca_group_mul`, prepared L1 τ, and
prepared cost-aware τ on 999 public-scalar cases: two registered j=0
subgroups (each on two public points), a complete scalar sweep of the
order-103 toy subgroup, and a 56-bit subgroup over `p=2^61−1`.
Boundary cases include zero, one, `r−1`, `r`, and `UINT64_MAX`.
The modified `test_curve` passed all 6,150 checks. The build used Apple clang
17 with `CA_WERROR=ON`. The exact source and command receipt is
[integration-check.json](integration-check.json), with
[test-curve output](integration-test-curve.log).

The full local suite passed 14 of 15 tests. `coord` failed at its local
socket `bind()` call; an independent Python socket bind on `127.0.0.1`
returned `PermissionError` (`errno=1`) in this sandbox. Its entire failing
output is retained in [integration-ctest.log](integration-ctest.log). The
full-suite result remains **incomplete**, pending CI on an environment that
permits localhost binding. No wall-time comparison was performed here.

## Frozen speed experiment to run after this protocol is published

The first target workload is a prepared rho-setup scalar panel, because the
same base or target point is multiplied by many public jump/restart scalars.
Freeze two exact j=0 curves: `glv-j0-32` with
`p=4294967377, a=0, b=15, r=23729779`, and the 56-bit subgroup
`p=2305843009213693951, a=0, b=7, r=53624256071278747`. For each curve,
take `ca_group_find_generator(..., seed=1)` and its multiple `37P` as the
two input points. Generate 4,096 scalar inputs per point with standard
SplitMix64: initial state is `20261004 XOR (curve_index << 32) XOR
point_index`, with indices 0 and 1 in the order written above; each draw
increments the state by `0x9e3779b97f4a7c15`, then applies the usual xor-shift
30/multiply `0xbf58476d1ce4e5b9`, xor-shift 27/multiply
`0x94d049bb133111eb`, and xor-shift 31. Reduce each output modulo `r` and
preserve generation order and any duplicates. Both arms receive identical
encoded points and scalar lists.

Prepare the nine seed and nine τ-seed points once per input point **outside**
the measured interval. Start the online clock immediately before the first
scalar's representative selection and stop after the last output point is
produced. Include all recoding, unit rotations, triplings, additions, and
conversions in the interval. Replay every output with ordinary `ca_group_mul`
and compute an ordered output digest outside the interval, recording replay
time separately. The two arms must report the same frozen input digest and
the same independently checked output digest. Also record preparation time,
total triples and additions, output failures, compiler and binary hashes.

Run the paired panel on the isolated benchmark service with at least five
paired repetitions per curve/point arm and alternating AB/BA order. Preserve
all raw repetitions and any failed preflight or noise gate. The headline is
the paired **prepared-panel** wall-time ratio, clearly labeled as such; a
single-call cold result, if added, is a separate workload that includes all
preparation. A faster modeled chain or an ordinary-host timing ratio does not
promote a CPU speedup claim. The `nohz_full`, exclusive partition, NUMA,
frequency, IRQ, and correctness receipt gates in
[ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md) apply.

## Frozen input and full C operation result

PR #252 was opened before [make_inputs.py](make_inputs.py) generated the four
4,096-scalar files in [inputs/](inputs/) under the protocol above. Each file
is exactly 4,096 unsigned 64-bit words in little-endian order; the binary
format keeps the exact frozen inputs compact in the PR.
[inputs.json](inputs.json) records each exact curve, public point, scalar-file
SHA-256, input digest, and independently generated reference output digest.
The [benchmark executable](bench.c) accepts `reference`, `baseline`, `cost`,
and later positional, batch, atlas, and fused modes as its first argument. It
prepares the τ seed table before its online
timer, then charges representative selection and the complete point path.
Every baseline/candidate output is replayed with `ca_group_mul` after the
timer; replay time is reported separately. [check_panel.py](check_panel.py)
ran both arms on the frozen inputs for **correctness and operation counts
only**. Its [native-panel.json](native-panel.json) retains raw stdout,
stderr, return codes, source hashes, and operation totals. All four cases
verified against the frozen output digests.

| Curve and point | Baseline weight | Cost-aware weight | Saved model weight |
| --- | ---: | ---: | ---: |
| `glv-j0-32`, generator | 518,207 | 485,166 | 6.38% |
| `glv-j0-32`, `37P` | 516,218 | 483,589 | 6.32% |
| 56-bit subgroup, generator | 1,213,102 | 1,168,091 | 3.71% |
| 56-bit subgroup, `37P` | 1,211,747 | 1,166,601 | 3.73% |

These are exact counts of the executed prepared C schedules under the frozen
weights. The local wall times appearing in raw stdout were obtained on an
unverified host and do not support a speedup claim. The 25-schedule search
cost is included in the benchmark's timer and will decide the actual result.

On a qualifying Linux host, build with `CA_BUILD_TAU_CHAIN_BENCH=ON`, run
[make_isolated_manifest.py](make_isolated_manifest.py) with that host's
absolute checkout, binary, isolated cgroup, CPU partition, execution CPU,
and NUMA node, then submit its JSON to `scripts/isolated_bench.py`. A local
schema check confirmed that the generated manifest passes the runner's
`require_manifest`; only the host-side preflight can authorize a measurement.

## Four-step residue atlas follow-up

The separate [residue-atlas protocol](RESIDUE_ATLAS.md) was committed before
the new input panel. [make_residue_atlas.py](make_residue_atlas.py) generates
the deterministic 7,429-byte [C atlas](../../src/generated/tau4_residue_atlas.h)
from the exact digit rule. The recoder reduces four τ digits per lookup and
preserves the same minimum-L1 representative and point schedule.

[make_atlas_inputs.py](make_atlas_inputs.py) froze four new 4,096-scalar
workloads in [atlas-inputs/](atlas-inputs/) and [atlas-inputs.json](atlas-inputs.json).
[check_atlas_panel.py](check_atlas_panel.py) replayed all 16,384 atlas point
outputs independently, compared each scalar's digit stream with the baseline
outside the timer, and matched each case's complete `triples`, `adds`, and
`rotations` totals. [atlas-panel.json](atlas-panel.json) retains the raw
results and source hashes. C tests additionally checked all 6,561 residue
pairs across signed translations and 10,000 random signed coefficient pairs.

| Frozen case | Triples in each arm | Adds in each arm | Rotations in each arm |
| --- | ---: | ---: | ---: |
| `glv-j0-32`, generator | 25,668 | 15,635 | 10,225 |
| `glv-j0-32`, `37P` | 25,715 | 15,621 | 10,211 |
| 56-bit subgroup, generator | 65,684 | 33,557 | 21,764 |
| 56-bit subgroup, `37P` | 65,641 | 33,531 | 21,830 |

The exact operation counts are unchanged, as intended; any benefit must come
from lower recoding overhead. Local wall times are exploratory because this
host lacks the isolation receipt required for a CPU speedup claim.

Generate a Linux-host manifest with `make_isolated_manifest.py --arm atlas`
and that host's checkout, binary, cgroup, CPUs, and NUMA node. The manifest
generator includes the protocol, input files, generator, and generated atlas
as hashed artifacts. The 4,096-scalar panel is a throughput experiment and
does not establish one-call latency.

## Fused eight-digit fixed-base follow-up

The [fused-pair protocol](FUSED_TAU_PAIRS.md) was committed and PR #260 was
opened before [make_tau8_pairs.py](make_tau8_pairs.py) generated the
[compact pair map](../../src/generated/tau8_pair_map.h) and before the new
[fused-inputs/](fused-inputs/) panel was materialized. The map enumerates
29,593 valid ordered pairs of four-step atlas patterns. Per point, the
candidate constructs one affine point for each valid pair and eight-digit
position, then applies one mixed addition per nonzero block. The benchmark
uses four blocks for `glv-j0-32` and six for `j0-56`, with exact positional
fallback for longer representatives.

[check_fused_panel.py](check_fused_panel.py) compared `pos-batch128` with
`fused-batch128` on four newly frozen 4,096-scalar workloads. All 16,384
fused outputs replayed against generic multiplication and matched the
independently frozen digests. [fused-panel.json](fused-panel.json) retains
the raw runs, failures, source hashes, operation counts, and setup figures.

| Frozen case | Positional adds | Fused adds | Adds saved | Fused table |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32`, generator | 15,563 | 8,325 | 46.51% | 3,787,904 B |
| `glv-j0-32`, `37P` | 15,571 | 8,331 | 46.50% | 3,787,904 B |
| 56-bit subgroup, generator | 33,527 | 19,445 | 42.00% | 5,681,856 B |
| 56-bit subgroup, `37P` | 33,456 | 19,391 | 42.04% | 5,681,856 B |

Every fused case used zero online unit rotations, zero fallbacks, and the
same 32 output inversions as the paired positional batch. Fused preparation
charged 116,640 or 174,960 pair additions, respectively, plus global
positional setup and normalization. Those are exact executed operation
counts; they do not establish a wall-time win. The raw local wall times are
exploratory because this host lacks a host-level isolation receipt. This
format targets repeated multiplication with a fixed public point, and any
new-target table setup must be charged inside a one-target rho solve.

Generate the Linux-host manifest with `make_isolated_manifest.py
--candidate-arm fused-batch128` and the host's own absolute checkout,
binary, cgroup, CPU partition, execution CPU, and NUMA node. A local schema
check passed `scripts/isolated_bench.py`'s `require_manifest`; only its
host-side preflight and noise gates can authorize a speedup claim.

## Six-unit orbit-folded fused-table follow-up

The separate [orbit protocol](FUSED_TAU_ORBITS.md) was committed in PR #264
before the generated [orbit map](../../src/generated/tau8_orbit_map.h), C
implementation, or new scalar files. Each nonzero fused-pair point belongs
to a six-element orbit under sign and the cheap `ω` endomorphism. The
candidate stores only 4,933 representatives per eight-digit position and
reconstructs the requested point with a unit action at lookup time.

[make_orbit_inputs.py](make_orbit_inputs.py) froze four fresh 4,096-scalar
workloads in [orbit-inputs/](orbit-inputs/) and
[orbit-inputs.json](orbit-inputs.json). [check_orbit_panel.py](check_orbit_panel.py)
verified all 16,384 folded outputs against the independent generic digest.
[orbit-panel.json](orbit-panel.json) retains raw output, failures, and hashes.
The folded and full tables used **identical online mixed-addition and
output-inversion counts** with zero fallbacks in every case. The folded
candidate trades unit rotations for lower setup and memory:

| Frozen case | Online adds in each arm | Folded rotations | Setup adds, full → folded | Affine table, full → folded |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32`, generator | 8,331 | 5,600 | 116,640 → 19,440 | 3,787,904 → 631,424 B |
| `glv-j0-32`, `37P` | 8,325 | 5,581 | 116,640 → 19,440 | 3,787,904 → 631,424 B |
| 56-bit subgroup, generator | 19,391 | 13,160 | 174,960 → 29,160 | 5,681,856 → 947,136 B |
| 56-bit subgroup, `37P` | 19,445 | 13,263 | 174,960 → 29,160 | 5,681,856 → 947,136 B |

The C small-order control independently checked every valid pair at two
positions against generic multiplication, including orbit reconstruction.
The local wall times in the raw receipt are exploratory. The isolated
manifest generator accepts `--candidate-arm fused-orbit-batch128` and pairs
it with `fused-batch128` on the same frozen inputs; its output passed the
runner's schema check. Whether smaller cache footprint and setup overcome
the added rotations requires a qualifying isolated Linux run, with
target-dependent table setup charged to a one-target rho solve.

## Budgeted hot-orbit proposal

The [hot-orbit protocol](HOT_ORBIT_TABLE.md) combines the folded table with
an exact positional miss path. Its [deterministic screen](screen_hot_orbits.py)
selects 2,048 two-digit orbits from separate training scalar streams and
records exploratory coverage in [hot-orbit-screen.json](hot-orbit-screen.json).
The implemented C path prepares the selected 2,048 orbit entries per block
and uses positional points for cold pairs. [hot-inputs.json](hot-inputs.json)
freezes new scalars and independent generic digests; [hot-panel.json](hot-panel.json)
retains the paired raw results. All 16,384 candidate outputs verify, and the
hot table retains 70.75–88.66% of the full folded table's saved online
additions while reducing its setup pair additions by about 58%. These are
operation results; local CPU times remain exploratory until an isolated run.

## Table-aware representative selection

The [two-representative protocol](TABLE_AWARE_HOT.md) in PR #275 freezes
the choice of the two shortest lattice representatives and selects the one
with fewer predicted hot-table additions. It reuses exactly the same
2,048-entry-per-block table as `fused-hot-batch128`. The second atlas recode
is charged inside the online timer.

The new [adapt2-inputs.json](adapt2-inputs.json) freezes four independent
4,096-scalar workloads created after the protocol PR opened.
[check_adapt_panel.py](check_adapt_panel.py) verifies every output against
generic multiplication and independently reimplements the selector in Python.
All 16,384 outputs and all four C addition totals agree. The new arm saves
5.61%–6.81% of online mixed additions over the ordinary hot arm with
identical table bytes and setup operations; [adapt2-panel.json](adapt2-panel.json)
retains the raw evidence and failures. The predeclared 3% addition gate
passes. The updated `test_curve` passed 407,658 checks, and all 14 locally
runnable CTest cases passed; `coord` requires a localhost bind denied in
this sandbox. No wall-time speedup is claimed on this contended host.
`make_isolated_manifest.py --candidate-arm fused-hot-adapt2-batch128`
pairs the two arms on identical scalar files for an isolated host.

## Demand-gated second recode

The [gated protocol](GATED_TABLE_AWARE.md) in PR #277 skips the second
atlas recode unless the first stream has a cold two-digit block or exceeds
the prepared span. [gated-inputs.json](gated-inputs.json) freezes four fresh
4,096-scalar cases created after the protocol PR opened.
[check_gated_panel.py](check_gated_panel.py) verifies every output against
generic multiplication and independently checks executed additions and
actual second-recode counts. The gated arm retains 81.35%–99.88% of the
always-two selector's addition saving while invoking the second recode on
20.51%–67.94% of nonzero scalars. Setup is identical across the three
arms; [gated-panel.json](gated-panel.json) retains the raw evidence.
The updated curve test passed 409,269 checks. An isolated host must compare
the gated arm separately with ordinary hot and with always-two before
judging CPU speed.

## Carry-steered eight-digit blocks

The [carry-steering protocol](CARRY_STEERED_TAU8.md) in draft PR #281
selects a lower-addition valid pair in the same residue modulo `τ^8` and
propagates the resulting exact carry. It uses the same prepared 2,048-orbit
hot table, plus a 13,122-byte static residue map. The fresh
[steer-inputs.json](steer-inputs.json) fixes four 4,096-scalar workloads.
[check_steer_panel.py](check_steer_panel.py) verifies all 16,384 results
against independent generic multiplication and matches every C addition
and substitution count to a separate Python recoder. Savings against the
ordinary hot arm are 5.63%, 5.95%, 11.73%, and 11.81%, exceeding the
prospective 3% gate in every case. Per-point setup operations and prepared
bytes are unchanged. [steer-panel.json](steer-panel.json) preserves raw
outputs and hashes. `test_curve` passed 410,876 checks. The isolated
manifest pairs this arm with the ordinary hot arm; no CPU wall-time or rho
speedup is claimed before a physical isolation receipt.

## Gated second representative after carry steering

The [gated dual protocol](GATED_DUAL_STEER.md) was frozen in draft PR #284
before its fresh inputs were generated. `fused-hot-steer-gated2-batch128`
keeps the carry-steered table and static map, and asks for the next-shortest
Eisenstein representative only if the first recode leaves a cold pair or
overflows its span. The second recode and any fallback are inside the online
timer. [gated2-steer-panel.json](gated2-steer-panel.json) preserves both arms'
raw outputs and counters for four 4,096-scalar cases; all 16,384 outputs and
all model predictions verify. The new arm saved 1.72%–2.56% of executed
mixed additions versus carry steering and recoded the second representative
on 5.96%–19.92% of nonzero scalars. Setup operations and bytes are identical.
`test_curve` passed 412,487 checks; the 14 locally runnable CTest cases
passed. `make_isolated_manifest.py --candidate-arm
fused-hot-steer-gated2-batch128` pairs the two arms on the frozen inputs.

The temporary RunPod CPU-pod preflight in
[runpod-isolation-preflight-20261004.json](runpod-isolation-preflight-20261004.json)
found cgroup v1, no isolated CPU partition, and no `nohz_full` CPUs. The pod
was stopped and deleted before any timing panel. These operation results
do not establish CPU speed or a complete one-target rho speedup.

## Tapered complete residue-orbit follow-up

The [tapered protocol](TAPERED_RESIDUE_ORBITS.md) was frozen in draft PR #287
before its fresh inputs were generated. `make_tau_wide_orbits.py` produces a
complete six-unit residue map for widths 8, 10, and 12. The native arm uses
the fixed schedules `(10,10,10,10)` and `(12,12,12,8,8)` and one mixed
addition per nonzero block. Its verified [tapered-panel.json](tapered-panel.json)
records 16,384 generic-matching outputs, raw runs, and independent operation
models. The new arm saves 3.76%–3.94% and 39.14%–39.16% online additions
against `fused-hot-steer-gated2-batch128`, but setup additions grow from
8,192 to 62,424 and 12,288 to 506,664. Prepared point tables grow from
262,144 to 1,259,904 bytes and 393,216 to 8,573,280 bytes. The local
`test_curve` passed 414,141 checks. Generate an isolated-host manifest using
`make_isolated_manifest.py --candidate-arm tapered-residue-orbit-batch128`;
the host must pass its isolation gate before any wall-time claim. The table
cost precludes a present claim about one-target rho benefit.

## Unit-folded orbit graph preparation

The [graph protocol](ORBIT_GRAPH_PRECOMPUTE.md) was frozen in draft PR #293
before native evaluation. `make_tau_wide_graph.py` verifies all 99,513 orbit
recipes and emits a predecessor graph. The graph builder constructs the same
point table as the direct builder, using one shifted-digit addition from a
smaller orbit point. [orbit-graph-panel.json](orbit-graph-panel.json) retains
eight paired cases on generator, `37P`, `101P`, and `103P` for both curves.
All 32,768 graph outputs match generic multiplication and online counters
match the direct arm. Setup additions fall from 62,424 to 39,096 and from
506,664 to 267,552, with 78,744 and 717,360 extra static recipe bytes.
Setup rotations fall from 63,194 to 44,453 and from 409,586 to 248,427.
The curve test matched all 307,287 prepared entries for generators on the
two curves and passed 722,512 checks. The host isolation gate still controls
any CPU wall-time claim.

## One-word orbit graph recipes

The [packed protocol](PACKED_ORBIT_GRAPH.md) was frozen in draft PR #297
before native evaluation. It maps all 99,513 exact predecessor recipes to
one 32-bit word each plus a 54-byte digit-slot map. The
[eight-point panel](packed-orbit-graph-panel.json) verifies 32,768 generic
outputs, identical curve-preparation and online operations, 39,368 and
267,910 candidate slot lookups, and recipe-byte totals of 39,426 and
358,734. All 307,287 prepared point entries for generator cases match the
stored graph builder; `test_curve` passed 1,030,887 checks. Both formats
are present in the paired binary, and no isolated CPU timing or standalone
binary-memory saving has been established.

## Batched affine graph wavefront

The [wavefront protocol](AFFINE_WAVEFRONT.md) was frozen in draft PR #299
before native evaluation. The [eight-point panel](affine-wavefront-panel.json)
matches all 1,229,148 prepared entries and 32,768 generic scalar outputs
against the packed graph, with identical graph-addition and online counters.
It trades three or four additional batch inversions and extra temporary
scratch for fewer modeled field operations per graph edge and no final
projective-to-affine normalization. The candidate is opt-in. The isolated
manifest uses per-point `prep_ms`; no qualifying host receipt or single-scalar
latency measurement exists yet.
