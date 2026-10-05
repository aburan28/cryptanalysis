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
