# Bounded τ-tail shortest-path oracle: prospective protocol

## Question

Can an offline shortest-path table over small Eisenstein coefficients reduce
the *evaluation* operations of prepared width-four τ scalar multiplication
without adding prepared curve points? The method deliberately pays for a
second online recoding, so an operation-model win is not a CPU speed claim.
The prior cost-aware representative search, residue atlas, and fused/tapered
batch schemes answer different questions. This arm holds the 25-representative
selection and the nine seed points of `baseline` fixed.

## Frozen candidate

The existing width-four digit table has 54 nonzero signed unit digits. For a
pair of τ positions, let `q=(a+bτ−d)/τ²`. There are three action kinds: no
digit, an even-position digit `d`, or an odd-position digit `τd`. The digit
set and one-nonzero-per-pair invariant are unchanged. The odd-position
choices retain only successors whose first coordinate is divisible by three;
this is the precise choice set of the exploratory screen. Each action uses
only the already prepared `seed` or `tau_seed` point and an optional unit
rotation. The online evaluator is the existing tripling plus mixed-add loop.

At pair phase `i mod 3`, an action costs 10 for a tripling unless it reaches
zero, 16 for a nonzero digit, and 1 for a nontrivial unit rotation. Those are
the predeclared operation-model weights in [README.md](README.md), not elapsed
times. An offline reverse Dijkstra pass finds a cheapest action to zero at
each reachable state `(a,b,i mod 3)` in `[-64,64]² × {0,1,2}`. The table has
`3 × 129² = 49,923` one-byte actions. Value 254 means unreachable, 255 is a
zero pair, 0..80 identifies an even digit's `(a mod 9,b mod 9)` slot, and
128..208 identifies an odd digit's slot. Unused slots never appear.

The candidate first follows the canonical recoder while either coefficient
is outside `[-64,64]`. It then follows the table until zero. It reuses the
canonical result if a state is unreachable, a bound or invariant fails, or
the complete candidate digit stream has no strictly lower weighted
evaluation cost. In particular, a modeled tie keeps `baseline`. The table is
not a curve-point table; it adds static code/data bytes, not point setup.
This recoder is intended for public scalars and has scalar-dependent lookup
and branches. It is not a constant-time private-key API.

`make_tau_tail_oracle.py` is the deterministic table generator. Its exhaustive
check follows every reachable table path to zero, validates exact integral
quotients and the odd restriction, checks the shortest-path cost identity at
each step, and detects cycles through strict cost decrease. Missing states
remain explicit. Re-running it must reproduce the checked-in header byte for
byte. Neither the generator nor its exploratory Python predecessors are
inside the online benchmark interval.

## Frozen independent panel

The development screen used only the first 128 scalars of older
`orbit-graph-inputs.json` files on each of two curves. The 64-bound choice,
weights, digit set, tie rule, and table shape were selected before the panel
below. That screen is design data only; it is not held-out evidence.

`make_tail_inputs.py` fixes a new SplitMix64 seed `20280105` and uses unbiased
64-bit rejection sampling. It freezes 4,096 public scalars for each of two
curves (`glv-j0-32`, `j0-56`) and four public base points (`P`, `37P`, `101P`,
`103P`). It records SHA-256 of each scalar file and the generic multiplication
output digest. No scalar from this fixture is inspected to tune the candidate
after it is frozen. The benchmark compares `baseline` and `tail-oracle` in
alternating order on every identical curve, point, and scalar file. For each
arm, all 4,096 points are independently replayed using generic group
multiplication and compared with the frozen digest. The verifier retains raw
stdout, stderr, exit status, source/build hashes, operation counts, and any
failure in `tail-panel.json`.

The acceptance gate is exact output on all eight cases, passing curve tests,
no regression in the predeclared aggregate weighted evaluation operation
score, and strictly lower score on at least one case. Report triples,
additions, rotations, table bytes, and any zero-yield cases. A lower modeled
score does not compensate for additional online recoding time. The local
host is contended; any `online_ms` in the receipt is exploratory. Promote a
CPU wall-time claim only after the host-level isolation and noise gates in
[docs/ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md) pass on the
same frozen inputs. Check prior art before claiming academic novelty.

## Reproduction

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau_tail_oracle.py
cmake --build build-cost-aware --target test_curve ca_tau_chain_bench -j 4
python3 experiments/prime-j0-cost-aware-chain/make_tail_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/check_tail_panel.py \
  --bench build-cost-aware/ca_tau_chain_bench \
  --test-curve build-cost-aware/test_curve
```

This protocol is frozen before executing the new candidate on the fresh
panel. Results and any deviations must be appended below, leaving this
prospective section intact.
