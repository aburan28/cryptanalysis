# Pre-gated τ-tail oracle: prospective protocol

## Question

The [bounded τ-tail oracle](TAIL_ORACLE.md) lowers a modeled curve-evaluation
cost, but its online path first builds a complete canonical digit stream and
then builds a candidate stream to decide whether to keep it. Can that decision
be moved offline without changing any selected digit, curve output, or
evaluation operation? If so, the duplicate online recode and two online
weighted-score scans can be removed. This arm still has scalar-dependent
branches and is for public scalars only.

## Frozen method and proof obligation

The original oracle's bound `64`, action table, candidate digit set, tie rule,
and weights `10 × triples + 16 × mixed additions + rotations` stay fixed.
`make_tau_tail_gate.py` computes the canonical tail's exact score for each
`(a,b,phase)` in `[-64,64]² × {0,1,2}`. It sets one bit precisely when the
existing shortest-path table reaches zero with a *strictly lower* score.
Unreachable states and ties have a zero bit. The generator yields 6,241 bytes
of gate data: 29,454 improving states, 13,413 tied or worse reachable states,
and 7,056 unreachable states. It must reproduce its checked-in header byte
for byte.

Both recoders follow the same canonical prefix until entering the bounded
tail. For a nonzero tail, every prefix pair lies below the top nonzero pair,
so each candidate pays the same `10 × prefix_pair_count` for tripling and the
same prefix additions/rotations. The tail phase fixes the unit-rotation
cost. Therefore the complete-stream score difference equals the precomputed
tail-only score difference. This is why the gate can make the original
mode-3 decision from one table bit before emitting any tail digit.

Mode 4 emits the canonical prefix once, reads the gate bit, and emits either
the canonical tail or the existing oracle's tail. It falls back to full
canonical recoding if a bound or action invariant fails. Mode 3 remains an
independent correctness reference. The direct curve test compares the two
digit streams byte for byte on its seeded scalar controls and compares their
tripling, mixed-addition, rotation, and point outputs against generic
multiplication. The new arm adds the 6,241 gate bytes to the 49,923 oracle
action bytes; it adds no prepared curve points.

## Fresh panel and gates

The previous `tail-inputs.json` scalars were used during design and are not
held-out evidence for mode 4. `make_tail_gated_inputs.py` fixes a new
SplitMix64 seed `20280106`, 64-bit rejection sampling, 4,096 public scalars
on each of two curves, and the four points `P`, `37P`, `101P`, `103P`. The
fixture records every scalar-file SHA-256 and the generic-output digest
before the new arm is run. The verifier alternates the order of `baseline`,
`tail-oracle`, and `tail-oracle-gated` on each case. It retains raw stdout,
stderr, exit status, source/build hashes, and exploratory elapsed times.

The acceptance gate is exact generic output on all 32,768 new scalars,
byte-identical mode-3/mode-4 recodings in the direct tests, identical
mode-3/mode-4 evaluation operations on each case, and strictly lower modeled
cost than baseline on every case. Report a failure or zero-yield row rather
than hiding it. The old operation score is deliberately preserved; the
online recoding workload is what changes. `online_ms` includes recoding but
this host is contended. No CPU speedup is claimed until a paired isolated
benchmark receipt passes the host-level gates in
[docs/ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md).

## Reproduction

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tau_tail_gate.py
cmake --build build-cost-aware --target test_curve ca_tau_chain_bench -j 4
python3 experiments/prime-j0-cost-aware-chain/make_tail_gated_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/check_tail_gated_panel.py \
  --bench build-cost-aware/ca_tau_chain_bench \
  --test-curve build-cost-aware/test_curve
```

This protocol and the fresh scalar fixture are committed before running the
new arm on that fixture. Append results below without changing the
prospective section.

## Fixture collision and invalidation (2026-10-05)

The first panel passed correctness and mode-3/mode-4 operation equality, but
its planned fresh-input claim failed. Seeds `20280105` and `20280106` differ
only in low bits also XORed with `point_index` (0..3). Consequently, the four
v1 scalar files on each curve are a permutation of the earlier
`tail-inputs.json` files. The v1 report, `tail-gated-panel.json`, is retained
as a diagnostic and must not be cited as held-out evidence or a second
independent trial. This was discovered before promoting its result.

## Replacement prospective v2 fixture

`make_tail_gated_v2_inputs.py` uses SplitMix64 seed
`0xA7395C41D8420F60`. It excludes, by scalar value on each curve, all
scalars from the frozen `orbit-graph-inputs.json`, `tail-inputs.json`, and
invalid v1 `tail-gated-inputs.json` fixtures, plus any scalar already
accepted into an earlier v2 point case. It checks every prior file SHA-256
against its manifest and records all prior-manifest hashes. The resulting
4,096 unique scalars per point are conditionally sampled from the remaining
subgroup scalars. This explicit exclusion changes the input law slightly;
it makes every v2 scalar unseen in the known design data. The verifier
independently checks the exclusion and uniqueness before running any arm.

The v2 acceptance criteria remain the original correctness, digit-stream,
operation-equality, and baseline-cost gates. The fixture and this deviation
are committed before evaluating `tail-oracle-gated` on v2. The report goes
to `tail-gated-v2-panel.json`. Reproduce it with:

```sh
python3 experiments/prime-j0-cost-aware-chain/make_tail_gated_v2_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/check_tail_gated_panel.py \
  --bench build-cost-aware/ca_tau_chain_bench \
  --test-curve build-cost-aware/test_curve \
  --fixture tail-gated-v2-inputs.json \
  --output tail-gated-v2-panel.json
```

## Disjoint v2 operation result (2026-10-05)

The v2 verifier confirmed every scalar is absent from all three pinned
design fixtures and is unique within its curve's four v2 point cases. All
three arms matched generic multiplication and the frozen digest on all
32,768 new outputs. The direct curve test passed 2,269,368 checks, including
exact mode-3/mode-4 digit-stream comparisons. The gated arm and original
oracle had identical tripling, mixed-addition, rotation, point-preparation,
and output-inversion counts on every case. The candidate uses the same
49,923-byte oracle and 6,241 gate bytes, with no additional prepared points.
The final v2 receipt also compares both recoders' digit streams on every
frozen scalar outside the timed interval; all 32,768 stream checks passed.
The complete CTest suite passed all 15 cases on the local macOS host with
loopback permission for the coordinator test.

| Curve and point | Baseline weighted cost | Original = gated weighted cost | Gated saving |
| --- | ---: | ---: | ---: |
| glv-j0-32, P | 513,803 | 475,554 | 7.44% |
| glv-j0-32, 37P | 514,254 | 476,857 | 7.27% |
| glv-j0-32, 101P | 517,048 | 477,297 | 7.69% |
| glv-j0-32, 103P | 517,847 | 478,230 | 7.65% |
| j0-56, P | 1,212,693 | 1,177,466 | 2.90% |
| j0-56, 37P | 1,212,169 | 1,177,362 | 2.87% |
| j0-56, 101P | 1,214,813 | 1,178,945 | 2.95% |
| j0-56, 103P | 1,213,363 | 1,178,471 | 2.88% |

[tail-gated-v2-panel.json](tail-gated-v2-panel.json) preserves each raw run,
the exclusion result, source and binary hashes, all operation counts, and
exploratory `online_ms`. The pre-gated recoder removes duplicate work in its
control flow, but the local times give no stable wall-time ordering against
either arm. An isolated, paired full-scalar run is still required before
claiming CPU speed.
