# Orbit-pair point dictionary: prospective scalar experiment

## Question

The [two-digit τ-pair policy](TAIL_DOUBLE_PAIR.md) can save tripling steps,
but evaluates a pair with two nonzero digits using two mixed point additions.
Can a small prepared dictionary turn each such pair into **one** mixed
addition, then let a new shortest-path search exploit that lower pair cost?
This is a public-scalar, repeated-fixed-point experiment on the same two
ordinary prime-field `j=0` curve instances. It does not claim academic
novelty, CPU speed, or an end-to-end rho speedup.

## Exact algebra and point table

Write `τ=1−ω`, with `ω³=1` and `τ²=−3ω`. A two-position contribution is
`c=d_even+τ d_odd`. Each digit is zero or one of the existing 54 signed
unit-orbit digits. The 3,025 raw pairs collapse to 727 exact contributions.
The 726 nonzero contributions are closed under multiplication by the six
units `±ω^j` and form **121 orbits**. Select one fixed representative per
orbit. For the 18 orbits with a single even or odd digit, select the existing
seed or τ-seed point as representative so their rotation count matches the
current evaluator. For other orbits, use the lexicographically least
coordinate pair. Prepare one affine point `R_i=c_i P` per representative.
Construct it from the existing prepared even/odd seed points with zero or
one additional mixed addition, then batch-normalize all 121 points with one
inversion. Record this point-dependent setup separately, including the
original 18-seed preparation. Some representatives may map to the identity
on a small-order point; preserve exact output in that case.

At pair position `q`, use the contribution's stored orbit, unit power, and
sign to add `(-ω)^q c_i P` after tripling the accumulator. Every nonzero pair
therefore costs one mixed addition and at most one unit rotation online.
The pair word uses seven orbit bits, two unit-power bits, and one sign bit;
special words denote zero and unreachable states. This is a different
evaluation algorithm from adding the pair's two digits separately.

## Offline search and online boundary

Reverse Dijkstra search covers `[-64,64]² × {0,1,2}`. An edge removes one
of the 727 contributions and divides exactly by `τ²`. The frozen score is
`10 × triples + 16 × mixed additions + unit rotations`. A nonzero pair
costs 16 plus its phase rotation; a tripling costs 10 when a higher pair
remains. The generator follows every reachable path to zero, checks exact
integer quotients and strictly decreasing costs, and proves the new cost is
no greater than the preceding two-digit policy at every state. A gate chooses
the fused path only if it strictly beats canonical recoding; ties keep the
canonical tail. The common canonical prefix is emitted once. The policy
folds states under simultaneous sign change and uses one byte per state
with phase/residue-local action dictionaries. The generated header contains
the exact recipes, orbit coordinates, prefix one-digit words, gate, and
bounded policy. Its static bytes and the 121-point table are reported
separately. The generated static arrays total 33,289 bytes; the affine point
table adds 3,872 bytes per prepared base point, plus the existing seed structure.

The primary experimental online interval starts with the first scalar
reduction after a point's dictionary is ready and ends with the last affine
output for 4,096 public scalars. It includes all recoding, policy lookups,
unit transforms, tripling, mixed additions, conversions, and output storage.
It excludes point-dependent dictionary preparation and independent scalar
replay; report both separately. A one-target rho solve must charge any
dictionary built from a new target point to that target's online interval.
Batch throughput cannot stand in for a one-target rho result.

## Design screen and prospective gate

The [design-data screen](tail-pair-fused-screen.json) uses two old scalar
files from `tail-inputs.json`, 4,096 each. It finds 45,129 reachable states,
40,566 with lower modeled cost than the old two-digit policy and none with
higher cost. Against the old policy's canonical gate, the fused tail saves
25,769 weighted units on `glv-j0-32` and 25,646 on `j0-56`, with 2,562 and
2,394 winning scalars. These figures exclude point setup, online recoder
time, and cache effects. They justify native implementation only.

Before running the native candidate, freeze eight 4,096-scalar cases on the
two curves and points `P`, `37P`, `101P`, and `103P`. Generate with SplitMix64
seed `0xD1B54A32D192ED03`, 64-bit rejection sampling, and value rejection
against all earlier orbit-graph and τ-tail fixtures, including
`tail-double-inputs.json`. Freeze each generic reference output digest and
all file hashes. Keep the protocol, generator, design screen, and input
fixture in a commit before the first native candidate run.

The paired arms are `tail-double-residue` and `tail-pair-fused`, rotated on
identical inputs. Preserve failed, timed-out, OOM, and zero-gain cases.
Outside the online timer, reconstruct every candidate scalar exactly from
its pair words, assert its modeled score is no greater than the previous
arm, and independently replay every output with generic multiplication.
The acceptance gate is verified output on all 32,768 scalar-point inputs,
correct preparation on boundary/small-order points, and strictly lower
aggregate weighted evaluation score in **all eight cases**. Report setup
triples/additions/rotations/inversions, table bytes, online operations,
online and setup intervals, verification time, and raw stdout/stderr/status.
Local wall times are exploratory on this contended macOS host. Promote a CPU
wall-time claim only after at least five paired AB/BA repetitions pass the
[host-level isolation gate](../../docs/ISOLATED_BENCHMARKS.md).

The repository already has a much larger [fused eight-digit positional
table](FUSED_TAU_PAIRS.md). Broader τ-adic digit-set optimality and
precomputation are established in [Heuberger and Krenn's
analysis](https://arxiv.org/abs/1110.0966) and [Heuberger and Mazzoli's
Eisenstein digit-set work](https://eprint.iacr.org/2013/705.pdf). Whether
this small orbit-pair dictionary plus weighted search is publishably new
requires a dedicated prior-art comparison.

## Reproduction after implementation

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau_pair_fused.py
python3 experiments/prime-j0-cost-aware-chain/screen_tau_pair_fused.py
python3 experiments/prime-j0-cost-aware-chain/make_tail_pair_fused_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
```

Append held-out results below without changing this prospective protocol.
