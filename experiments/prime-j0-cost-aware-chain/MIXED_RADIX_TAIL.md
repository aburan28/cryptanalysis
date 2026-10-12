# Exact mixed-radix tail on prime-field j=0 curves

## Question and scope

Can a short Eisenstein tail use cheap **τ², τ, and binary** steps together,
instead of forcing every position through a τ² pair step? This experiment
keeps the existing lattice reduction, canonical high-order pair recoder,
727-word pair digit catalog, and 726-point prepared table. Only a bounded
tail changes. The output is still an exact scalar representation.

The idea is distinct from changing the 3-adic action selected by the periodic
pair atlas: the evaluation may now double or apply one τ between mixed
additions. Broad double-base scalar multiplication and τ-adic methods have
prior art, including [Avanzi and Sica's Koblitz-curve double-base
work](https://eprint.iacr.org/2006/067.pdf) and
[imaginary-quadratic digit-set analysis](https://arxiv.org/abs/1110.0966).
This design screen does not establish academic novelty, native performance,
or a CPU speedup.

## Exact bounded-state graph

Represent a scalar as `a+bτ`, with `τ²=3τ−3`. A high-order τ² step may use any
of the existing 727 pair words. A single τ or binary step uses zero or one
of the six Eisenstein units `±1, ±ω, ±ω²`, which are already points in that
catalog. For a quotient `q` and digit `d`, the predecessor is one of

```text
s = τ² q + d       τ²(a,b) = (−3a−9b, 3a+6b)
s = τ  q + d       τ (a,b) = (−3b, a+3b)
s = 2  q + d       2 (a,b) = (2a, 2b).
```

Build a directed graph on all `|a|,|b|≤64`, rooted at zero. The fixed model
charges `10` for a τ² step, `6` for a τ step, `8` for a double, and `16` for
a nonzero mixed-add digit; the initial nonzero digit has no radix-step cost.
Reverse Dijkstra finds a least-cost path within this square. The graph has
positive edge costs, so following a stored predecessor strictly decreases
the distance until zero. Equal-cost ties prefer τ², then τ, then doubling,
and then the lower word code. Every reachable path is reconstructed using
the exact integer recurrences and rescored. The generated action map stores
one 12-bit `(kind, word)` code in a `uint16_t` per state: **33,282 bytes**.

The pure τ² tail oracle reaches 15,043 of the 16,641 bounded states. The
mixed graph reaches **all 16,641**, and has a strictly lower modeled cost
on 8,602 states that the pure oracle reaches. The
[generated map](../../src/generated/tau_pair_mixed_radix_tail.h) SHA-256 is
`e113fb064e593723148763daa35d5837a3e908e16bf0fa6d558f756fc3093795`.
The [read-only auditor](audit_mixed_radix_tail.py) checks every map path and
the Bellman inequality for every legal graph edge, as well as the scalar
rows and source hashes.

## Full scalar screen on older inputs

For each reduced representative, take exactly the same canonical τ² steps
until the old bounded-tail oracle is reachable. Replace that tail with the
mixed path and reverse the resulting action list for evaluation. Exact
integer reconstruction is checked for every scalar. The comparator is the
same canonical high path with the old pure τ² tail. The already-published
single-pass first-word gate is shown as a second diagnostic comparator.
No new held-out scalar was used here.

The [screen](screen_mixed_radix_tail.py) processed all 4,096 scalars in each
of the older point-0 and point-1 files on both curves. The
[raw CSV](mixed-radix-tail-raw.csv) retains every scalar, case, score, and
operation count. The [summary](mixed-radix-tail-screen.json) pins its hash,
the map hash, input files, source files, graph model, and four totals.

| Curve | Point | Canonical score | First-word score | Mixed score | Saving vs canonical | Saving vs first-word |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 0 | 431,560 | 421,960 | 403,540 | 6.49% | 4.37% |
| glv-j0-32 | 1 | 431,210 | 421,664 | 402,474 | 6.66% | 4.55% |
| j0-56 | 0 | 1,124,088 | 1,111,934 | 1,095,048 | 2.58% | 1.52% |
| j0-56 | 1 | 1,121,712 | 1,113,130 | 1,093,962 | 2.47% | 1.72% |

These are modeled group-operation scores. Recoding, graph-map lookups,
memory traffic, table preparation, output conversion, and platform behavior
are absent from the score. The native implementation must charge all of
those inside the appropriate measured interval. A group-operation saving
is not a CPU speedup.

## Prospective native gate

Freeze this method, generated map, old-data raw rows, and audit before a
native implementation. Use the existing checked C formulas for τ² tripling,
single τ, and doubling; retain the portable path. The evaluator must track
the unit phase induced by every τ² step while applying τ and binary steps,
and select the corresponding already-prepared affine digit. Count each
radix kind, mixed addition, map lookup, fallback, static bytes, prepared
bytes, and output conversion. Compare C action traces to the generated map
on all 16,384 old scalars before generating new inputs. Verify independent
generic point multiplication on each scalar and test zero, subgroup-order
multiples, all 16,641 bounded states, small-order inputs, and the τ kernel.

Use a new SplitMix64 64-bit rejection fixture with seed
`0x7E31B642C5D908AF`: 4,096 scalars each for `P`, `37P`, `101P`, and
`103P` on both curves. Exclude zero, out-of-subgroup values, every scalar
in prior fixtures including `firstword-pair-inputs.json`, and earlier
accepted scalars on the same curve. Commit the generator, fixture hashes,
generic-reference output digests, and the paired runner before either arm
runs. Preserve every failure and pair the same point, input, resource
envelope, and build. The primary comparator is the single-pass canonical
pair arm; run the first-word arm on the same fixture as a secondary
comparison. The prospective operation gate requires verified outputs and
a strictly lower mixed score than **both** comparators in all eight cases.

The online interval starts at the first scalar reduction after input
loading and 726-point preparation, and ends after the last affine output.
It includes map reads, heterogeneous recoding, all group operations,
conversion, and storage. Report preparation and the extra 33,282 static-map
bytes separately. An isolated CPU wall-time claim requires at least five
paired AB/BA repetitions and a qualifying host-level receipt from the
[serial service](../../docs/ISOLATED_BENCHMARKS.md). Earlier Mac timing and
this old-data operation screen are exploratory. For a one-target rho use,
charge any target-dependent preparation inside that target's online solve;
this repeated fixed-point panel does not establish a rho speedup.

Reproduce the old-data screen and audit without Sage:

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_mixed_radix_tail.py --samples 4096
python3 experiments/prime-j0-cost-aware-chain/audit_mixed_radix_tail.py
```

## Held-out native result

The native evaluator and differential controls were frozen in commit
`3b9db27b`. The new scalar fixture and three-arm runner were frozen in
commit `16287e02` before any pair arm ran. The fixture uses the stated seed
and contains 32,768 new scalars. Its manifest SHA-256 is
`adf881607a1cb3cc8b50a92b6b54265aabe8a4bc6ff9614281f2b8f8decb593f`.
The [fixture replay](check_mixed_radix_inputs.py) confirms disjointness from
all prior fixture scalars, the generator law, file hashes, and the eight
generic-reference point-output digests.

The [old-data native differential receipt](mixed-radix-native-design.json)
records **16,384 exact C action streams** matching the frozen Python map.
The C curve suite reconstructs all 16,641 bounded map states, compares mixed
point outputs against generic multiplication, covers zero and subgroup-order
multiples, small-order points, and directly checks the rational `τ` kernel.
The 3-torsion kernel check exercises `τ(P)=O` directly; the complete pair
preparation requires a subgroup where the lattice recoder is defined.

The [held-out raw panel](mixed-radix-native-panel.json) retains all 24 arm
statuses, fields, source and binary hashes, and exploratory timing values.
The [read-only panel audit](audit_mixed_radix_panel.py) passed. Weighted
group-operation scores use exactly `10·triples + 6·τ + 8·doubles + 16·adds`.
All 24 outputs were independently verified against the frozen generic
digests. The prospective gate, which required mixed to beat **both**
comparators in every case, passed 8/8.

| Curve | Point | Canonical | First-word | Mixed | Saving vs canonical | Saving vs first-word |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 0 | 433,986 | 424,878 | 404,502 | 6.79% | 4.80% |
| glv-j0-32 | 1 | 432,398 | 423,484 | 403,726 | 6.63% | 4.67% |
| glv-j0-32 | 2 | 431,800 | 424,230 | 402,866 | 6.70% | 5.04% |
| glv-j0-32 | 3 | 433,928 | 424,452 | 405,108 | 6.64% | 4.56% |
| j0-56 | 0 | 1,123,174 | 1,114,796 | 1,094,352 | 2.57% | 1.83% |
| j0-56 | 1 | 1,122,268 | 1,113,542 | 1,093,680 | 2.55% | 1.78% |
| j0-56 | 2 | 1,121,830 | 1,114,390 | 1,092,954 | 2.57% | 1.92% |
| j0-56 | 3 | 1,121,936 | 1,114,762 | 1,093,660 | 2.52% | 1.89% |

The mixed implementation uses the same 726 prepared points and 23,232-byte
point table as the comparators. Its static maps occupy 99,853 bytes in
total, including the old tail map needed for the frozen entry rule;
canonical uses 68,029 bytes and first-word uses 68,157. The extra map reads,
recoding, and heterogeneous steps are included in the recorded online
interval, but their Mac wall times are exploratory because this host has no
host-level isolation receipt. No CPU, rho, or academic-novelty speedup follows
from this operation panel. A controlled CPU claim still requires the serial
isolated service and at least five paired AB/BA repetitions.

Reproduce the native controls and read-only audits without Sage:

```sh
cmake -S . -B build-cost-aware -DCMAKE_BUILD_TYPE=Release -DCA_WERROR=ON -DCA_BUILD_TAU_CHAIN_BENCH=ON
cmake --build build-cost-aware --target test_curve ca_tau_chain_bench ca_tau_chain_design64 -j 4
build-cost-aware/test_curve
python3 experiments/prime-j0-cost-aware-chain/check_mixed_radix_inputs.py --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/audit_mixed_radix_panel.py --bench build-cost-aware/ca_tau_chain_bench
```
