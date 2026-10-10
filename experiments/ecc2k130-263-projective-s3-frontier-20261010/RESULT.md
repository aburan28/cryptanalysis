# A single free leaf pair sustains SAT search; one free projective state solves

On both the ECC2K-130 source and its verified oriented degree-263 descendant,
releasing just one leaf's 131-bit `x` and 131-bit `z` words from a checked
six-summand cancellation witness reached CryptoMiniSat's 120-second internal
limit. Releasing just one projective intermediate instead produced a SAT model
on each curve. Independent replay checked all native-XOR and ordinary-clause
constraints and reconstructed the signed point sum to the exact group target
for all four SAT models. This identifies the leaf-coordinate equations and
their link to the S3 tree as the next place to improve propagation.

The [precommitted protocol](PROTOCOL.md) and
[eight input receipts](runs/R1/source_cells.json) use proposal `Q1420`, the
same one-target workload `eee7f6ee5f6b`, and `B=16,772,828` distinct
subgroup-usable W24 points on each curve. Curve IDs are
`EC1N131Ckb1h136f03e58c98` and `EC1N131Cbinh833014327b07`.
Every row keeps the parent base XCNF, six selected masks, target lift, solver
binary SHA-256 `a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
and one-thread policy fixed; only the named unit block changes. A leaf cell
fixes 1,984 of the parent's 2,246 external bits, while a state cell fixes
2,114. The source XCNF has 340,821 variables and the descendant XCNF
345,266. The eight full input SHA-256 values, unit deltas, and constraint
counts are in the per-curve receipts. Protocol/source commit `354991a60`
and input commit `53fcba36385ed0fc09dd92d46aefea7583f6c918` precede all
solver measurements.

| Curve | Released block | Audited status | Solver wall s | Peak sampled RSS MiB | Final conflicts | Restart rows |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Source | leaf 0 x/z | `BOUNDED_UNKNOWN` | 122.809 | 169.297 | 887,645 | 1,438 |
| Source | leaf 5 x/z | `BOUNDED_UNKNOWN` | 123.204 | 238.344 | 861,022 | 1,429 |
| Source | state 0 x/finite | `SAT_VERIFIED_GROUP` | 0.539 | 133.609 | 0 | 1 |
| Source | state 3 x/finite | `SAT_VERIFIED_GROUP` | 0.530 | 127.547 | 4 | 1 |
| Descendant native | leaf 0 x/z | `BOUNDED_UNKNOWN` | 121.900 | 229.453 | 955,100 | 1,481 |
| Descendant native | leaf 5 x/z | `BOUNDED_UNKNOWN` | 124.273 | 229.703 | 782,430 | 1,328 |
| Descendant native | state 0 x/finite | `SAT_VERIFIED_GROUP` | 0.532 | 130.938 | 0 | 1 |
| Descendant native | state 3 x/finite | `SAT_VERIFIED_GROUP` | 0.532 | 142.750 | 13 | 1 |

Each bounded row ended with explicit `s INDETERMINATE`, exit code 15, and
the exact conflict count above; neither external 150-second wall nor 4-GiB
RSS guard fired. The SAT rows returned exit code 10. On the source, each SAT
model passed 337,062 ordinary clauses and 227,932 native XORs; on the
descendant it passed 336,504 and 232,515 respectively. All four group
replays found two matching sign assignments and the exact archived target.
The [archive-only audit](runs/R1/audit.json) rebuilds all eight inputs from
the parent compressed base and committed unit deltas, verifies every
source/input/transcript hash, and checks each SAT assignment and group sum.
An independent rerun of that auditor produced a byte-identical JSON result.

The first sandboxed source/leaf-0 invocation failed at its `ps` RSS preflight
before solver search. Its [failure receipt](runs/R1/source_leaf0_preflight_attempt0.json),
empty stdout, and complete stderr retain the `PRODUCER_FAILURE`. The unchanged
frozen input then ran with local permission for `ps`; the row in the table is
that monitored run. The [environment record](runs/R1/environment.json) gives
macOS 26.6, Apple M4 Pro, Python 3.13.1, binary identity, timing boundary,
and monitoring method. There is no host-isolation receipt, so the wall times
are exploratory stage measurements; the decisive observation is the paired
status and independently verified model under the frozen cap.

The next frozen gate should release **only `x` or only `z`** for leaf 0 and
leaf 5 on both curves, retaining the other coordinate and all S3 states at
the same witness values. The leaf equations are `w z = 1` and
`u(x + alpha) = alpha`, with `w` and `u` linear in the selected mask. This
split distinguishes the inverse-of-`w` constraint from the inverse-of-`u`
constraint and its S3 coupling. If one alone stalls, test a compact
functional or learned inverse for that coordinate against the exact
relational circuit. The prior [fully functional W24/m6 result](../ecc2k130-w24-functional-s3-20261006/RESULT.md)
grew the full XCNF 20.448-fold and reached its planted 30-second cap, so
the next change should target one measured subcircuit rather than replacing
the entire tree. A passing selective control would then move to one frozen
ordinary query and, only after a verified relation, the equal-B held-out
yield/rank screen. `candidate_id` stays `null` while natural relation yield,
rank, matrix solve, target descent, and one-target online IC costs are unset.

Reproduce the audit from committed archives with:

```sh
python3 -B experiments/ecc2k130-263-projective-s3-frontier-20261010/audit.py \
  --scratch-dir /private/tmp \
  --out /private/tmp/s3-frontier-audit-replay.json
cmp /private/tmp/s3-frontier-audit-replay.json \
  experiments/ecc2k130-263-projective-s3-frontier-20261010/runs/R1/audit.json
```
