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

## Held-out operation result (2026-10-05)

The frozen generator reproduced SHA-256
`fa5d1600004d25acbedcc0ec72e5c89b6438194c742a2ee4e17fd521f5263d3d`
for the generated header. Its exhaustive check found 42,867 reachable and
7,056 unreachable states; the longest checked path was five τ pairs. The
unreachable cells are explicit fallback markers. The fresh eight-case panel
passed: both arms matched generic scalar multiplication and the frozen output
digest for all 32,768 curve outputs. The direct curve test passed 2,263,268
checks. The full CTest suite had 14 passes and a coordinator loopback-bind
failure under the sandbox; rerunning that one test with loopback permission
passed, giving 15/15 passing test cases across the two executions.

Each row aggregates 4,096 public scalar multiplications. Costs are the
predeclared `10 × triples + 16 × mixed adds + rotations` model, with the same
per-point prepared seed table in both arms. The tail arm adds 49,923 static
action bytes and no prepared curve points.

| Curve and point | Triples, baseline → tail | Mixed adds, baseline → tail | Weighted cost, baseline → tail | Saving |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32, P | 25,612 → 21,957 | 15,593 → 15,563 | 515,792 → 477,193 | 7.48% |
| glv-j0-32, 37P | 25,703 → 21,933 | 15,651 → 15,603 | 517,625 → 477,520 | 7.75% |
| glv-j0-32, 101P | 25,702 → 21,954 | 15,666 → 15,622 | 517,960 → 478,139 | 7.69% |
| glv-j0-32, 103P | 25,641 → 21,965 | 15,614 → 15,574 | 516,483 → 477,446 | 7.56% |
| j0-56, P | 65,679 → 62,270 | 33,525 → 33,497 | 1,215,011 → 1,178,788 | 2.98% |
| j0-56, 37P | 65,639 → 62,320 | 33,437 → 33,404 | 1,213,053 → 1,177,590 | 2.92% |
| j0-56, 101P | 65,558 → 62,315 | 33,511 → 33,481 | 1,213,576 → 1,179,146 | 2.84% |
| j0-56, 103P | 65,588 → 62,311 | 33,539 → 33,523 | 1,214,505 → 1,179,738 | 2.86% |

All eight cases passed the prospective operation gate. [tail-panel.json](tail-panel.json)
retains rotations, exact outputs, source and binary hashes, raw execution
rows, and exploratory timings. Local `online_ms` values varied enough to
change which arm appeared faster across points; no wall-time winner is
reported. The oracle's second recode and lookups are charged to that interval
and may overwhelm the saved curve operations. The next empirical gate is an
isolated, paired `baseline`/`tail-oracle` run using the manifest service.
Related work on [τ-adic wNAF weight
optimality](https://arxiv.org/abs/1110.0966), [symmetric digit
sets](https://pmc.ncbi.nlm.nih.gov/articles/PMC4144834/), and [dynamic
programming for minimal-weight digital
expansions](https://dmtcs.episciences.org/en/articles/3009) means this
implementation result does not establish a new mathematical recoding result.

## Rho relevance

The j=0 `glv_rho_solve` path in `src/curve.c` performs scalar multiplications
when it builds its walk-multiplier table and starts or restarts walks. Its
repeated walk step uses batched point additions. This tail oracle therefore
cannot reduce the cost of every rho step by the percentages above. Wiring an
opt-in public-scalar backend into setup and restarts would need a paired,
verified one-target rho experiment that charges preparation and all restarts.
The current PR leaves rho's default walk and scalar backend unchanged until
that end-to-end benefit is established on an isolated host.
