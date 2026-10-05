# Two-digit τ-pair shortest paths: prospective protocol

## Question and exact candidate

The [pre-gated τ-tail oracle](TAIL_GATE.md) limits every aligned pair of τ
positions to at most one nonzero digit. A tripling costs 10 in the frozen
operation model, whereas one mixed addition costs 16. Can a pair with *two*
nonzero digits sometimes remove enough higher tripling steps to lower the
complete prepared-scalar evaluation cost? This candidate reuses exactly the
same nine seed points and their nine τ images. It does not add a prepared
curve point. It is an opt-in public-scalar research mode; its branches and
table accesses are scalar-dependent.

Let `τ=1−ω` and write one pair's contribution as `d_even + τ d_odd`, where
each digit is zero or one of the existing 54 signed unit-orbit digits. For
state `z=a+bτ`, the successor is the exact integer quotient
`q=(z−d_even−τ d_odd)/τ²`. An action is valid when both coordinates of the
numerator are divisible by three. The action set has `1+54+54+54²=3,025`
raw choices, including zero, one-digit, and two-digit pairs. Many have the
same exact contribution. For each of the three unit-rotation phases,
`make_tau_tail_double.py` keeps the cheapest realization of each contribution,
with a stable tie rule; this leaves 727 contributions per phase.

An offline reverse Dijkstra search finds the cheapest path to zero at every
state in `[-64,64]² × {0,1,2}`. A pair edge costs 10 if its successor is
nonzero, plus 16 per nonzero digit and one per nontrivial unit rotation. This
matches the prepared evaluator's predeclared `10 × triples + 16 × mixed adds
+ rotations` score. The generator follows every reachable path to zero,
checks exact integral quotients, strictly decreasing costs, and each chosen
edge's cost identity. It also verifies that no state costs more than the
previous restricted one-digit oracle, whose actions are a subset. The
generated table contains 49,923 two-byte pair actions (99,846 bytes) and a
6,241-byte gate bitset. The gate chooses the candidate only when its tail
score is strictly lower than canonical recoding; ties keep canonical. The
common canonical prefix is emitted once. Its modeled score difference
cancels from the choice exactly as established in [TAIL_GATE.md](TAIL_GATE.md).

The evaluator triples its accumulator once per non-leading pair and may add
the even prepared point, the odd prepared point, or both, applying the same
unit rotation and sign rule to each. The result is no longer claimed to be
a width-four non-adjacent form: two digits in one pair are intentionally
allowed. The online interval includes all recoding, table lookups, curve
operations, and affine conversion. The table generator and point preparation
remain separate setup work.

## Design-data screen

The exact offline screen in [tail-double-screen.json](tail-double-screen.json)
used 4,096 scalars per curve from the already studied `tail-inputs.json`
fixture. Those scalars are *design data*, not held-out validation. The
two-digit policy lowered the modeled tail score of 1,487/4,096 small-curve
scalars and 1,505/4,096 larger-curve scalars beyond the restricted oracle;
extra saved weight was 11,953 and 12,020 respectively. The generator found
45,129 reachable states and 17,628 states cheaper than the restricted
policy. These diagnostics justify implementing a native arm but imply no CPU
speedup. Related work on [τ-adic wNAF
optimality](https://arxiv.org/abs/1110.0966) and [dynamic programming for
minimal-weight expansions](https://dmtcs.episciences.org/en/articles/3009)
means academic novelty is unproven.

## Frozen independent panel and gates

`make_tail_double_inputs.py` fixes SplitMix64 seed `0xC6A09E667F3BCC91`
and 64-bit rejection sampling. It excludes every scalar value from the
frozen `orbit-graph-inputs.json`, `tail-inputs.json`, invalid
`tail-gated-inputs.json`, and valid `tail-gated-v2-inputs.json` design
fixtures, plus any earlier accepted scalar on the same curve. It records and
verifies the prior file hashes. The result is 4,096 unique public scalars
on each of two curves and four points (`P`, `37P`, `101P`, `103P`), with
generic multiplication output digests frozen before the new arm is run.
The verifier independently rechecks scalar exclusion and uniqueness.

The paired arms are `baseline`, `tail-oracle-gated`, and `tail-double`, run
in rotating order on each exact point and scalar file. Each result is
independently replayed with generic multiplication. Outside the online
interval, every `tail-double` scalar is checked for exact Eisenstein-digit
reconstruction and modeled cost no higher than `tail-oracle-gated`; the
receipt counts these checks. The acceptance gate is verified output on all
32,768 scalars, identical per-point preparation counts, and **strictly lower
aggregate weighted evaluation cost than `tail-oracle-gated` on all eight
cases**. Preserve any failure, zero-yield case, timeout, or OOM. Report
triples, mixed additions, rotations, static bytes, and the raw command and
output for every arm. Local elapsed times are exploratory because this host
has no host-level isolation receipt. An isolated paired run through
[docs/ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md) is required
before any CPU speedup claim. No end-to-end rho claim follows from this
scalar panel; rho's repeated walk step uses point additions.

## Reproduction

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau_tail_double.py
python3 experiments/prime-j0-cost-aware-chain/screen_tau_tail_double.py
cmake --build build-cost-aware --target test_curve ca_tau_chain_bench -j 4
python3 experiments/prime-j0-cost-aware-chain/make_tail_double_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/check_tail_double_panel.py \
  --bench build-cost-aware/ca_tau_chain_bench \
  --test-curve build-cost-aware/test_curve
```

This protocol, generator, design screen, and new generic-output fixture are
committed before the new candidate is evaluated on the frozen panel. Append
the results below without changing this prospective section.

## Held-out operation result (2026-10-05)

The frozen generator reproduced header SHA-256
`2f2ebd44ccaf5dda7abfa7abf91289a2b4075c255b0f32656319ae3f625205ad`.
Its exhaustive replay reached 45,129 bounded states, with at most four τ
pairs per policy path; the statewise cost was never higher than the
one-digit policy. The verifier independently confirmed scalar-value
disjointness from all four pinned design fixtures. On all 32,768 new
scalar-point inputs, `baseline`, `tail-oracle-gated`, and `tail-double`
matched generic multiplication and the frozen output digest. The new arm
passed 32,768 exact digit-reconstruction and modeled-nonregression checks
outside the online interval; the direct curve test passed 2,273,444 checks.
Point preparation and output-inversion counts matched across all arms.
The complete CTest suite passed all 15 cases on the local macOS host with
loopback permission for the coordinator test. Both paired isolated-runner
manifests (`baseline` versus `tail-double`, and `tail-oracle-gated` versus
`tail-double`) validated against the runner schema; no isolated job has run.

Each row aggregates 4,096 scalars. The score is the predeclared
`10 × triples + 16 × mixed additions + rotations`; it excludes online
recoder work and is not a wall-time measurement.

| Curve and point | Baseline score | One-digit score | Two-digit score | Extra saving vs one-digit | Saving vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32, P | 517,128 | 477,939 | 466,210 | 2.45% | 9.85% |
| glv-j0-32, 37P | 516,918 | 478,095 | 466,486 | 2.43% | 9.76% |
| glv-j0-32, 101P | 514,461 | 476,230 | 464,870 | 2.39% | 9.64% |
| glv-j0-32, 103P | 516,561 | 477,212 | 465,347 | 2.49% | 9.91% |
| j0-56, P | 1,214,457 | 1,179,148 | 1,167,428 | 0.99% | 3.87% |
| j0-56, 37P | 1,214,018 | 1,179,052 | 1,167,256 | 1.00% | 3.85% |
| j0-56, 101P | 1,212,044 | 1,177,190 | 1,165,242 | 1.01% | 3.86% |
| j0-56, 103P | 1,215,045 | 1,179,206 | 1,166,901 | 1.04% | 3.96% |

All eight cases passed the prospective operation gate. The [raw
receipt](tail-double-panel.json) retains triples, additions, rotations,
static bytes, every command's output and failure status, input/source/binary
hashes, and exploratory local timing. The two-digit policy replaces some
tripling steps with additional mixed additions; its compiled action and gate
data total 106,087 bytes, versus 56,164 for the pre-gated one-digit arm.
The extra table footprint and recoding can erase the evaluation-operation
saving on a CPU. No isolated host receipt or rho solve exists for this arm,
so neither a CPU wall-time nor an end-to-end rho speedup is claimed.
