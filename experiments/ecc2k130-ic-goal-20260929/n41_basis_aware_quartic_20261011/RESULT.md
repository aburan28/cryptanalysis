# Basis-aware quartic circuit for a public N41 relation query

The basis-aware field representation reduces the target-coupled, single-branch N41 formula from **120,929 to 72,710 AND gates** while preserving the exact quartic and public-point constraints. It also reduces native XOR rows from 75,634 to 36,843. Seven independent arithmetic cases, a satisfying full-formula assignment, and an independent curve-law replay of a 12-column relation check the construction. The unpinned public query completed its 60-second CryptoMiniSat limit with `BOUNDED_UNKNOWN`.

## Construction

Each source point has a six-bit seed in the rotated span of `t, ..., t^6` in `GF(2^41)` with modulus `t^41+t^3+1`. For a pair of source seeds, the sum has at most six known basis images. Their product has eleven diagonal basis images before reduction. The compiler retains these source-derived expressions as lists of Boolean wires multiplied by fixed field elements. It folds equal basis images by XOR and uses the `d_left*d_right` bilinear products when that is cheaper than a dense field multiplication. Wider expressions materialize to 41 coordinate bits and use the existing Karatsuba circuit. Frobenius squaring maps each fixed basis image without nonlinear gates. The shared sparse Horner order is `S,Z,a,Q,P` for each of three quartic blocks, followed by the same two S3 public-target links as the comparator.

The frozen [protocol](protocol.json) fixes curve `EC1N41Ckb1h023d9a38bbf7`, public point `(1458168294740,1672312028033)`, six rotations `0,5,10,15,20,25`, 384 usable factor-base points, 26 folded columns, 12 source positions, two target reciprocal lifts, one worker, a 120-second construction cap, a 60-second solver cap with five seconds of parent drain, and a 4 GiB combined RSS cap. The proposal remains `candidate_id: null` because a full relation-collection, final matrix, and target-DLP pipeline is not specified by this component experiment. Source hashes are frozen in the protocol before the control and public query.

## Exact circuit and bounded query

| Same public N41 point and source law | Shared Horner | Basis-aware | Basis-aware / Horner |
| --- | ---: | ---: | ---: |
| AND gates | 120,929 | 72,710 | 0.601 |
| Variables | 196,923 | 109,913 | 0.558 |
| CNF clauses | 369,488 | 224,831 | 0.609 |
| Native XOR rows | 75,634 | 36,843 | 0.487 |
| XCNF bytes | 9,304,582 | 7,468,648 | 0.803 |
| Public-query status at cap | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` | — |

The basis-aware quartics make 165 field-multiplication calls: 117 sparse products with 32,877 bilinear pair products and 48 dense products. Quartic compilation contributes 69,423 of the 72,710 AND gates. The [query receipt](query_result.json) records 1.151814125 seconds to construct the formula, 0.027046666 seconds to write and hash it, and 65.118846125 seconds in the bounded solver process, totaling 66.297707416 seconds. These are exploratory wall times on an unisolated host; the table reports exact circuit sizes, not a controlled wall-time speedup. Combined sampled RSS peaked at 146,931,712 bytes. The solver log shows active restarts and no terminal satisfiability answer before the parent stopped it. This outcome is censored evidence about natural relation search, not a proof of absence.

## Verification and next step

The [arithmetic replay](arith_replay.json) compares compiled quartic outputs with independent direct polynomial evaluation in seven fixed cases. The [control receipt](control_result.json) validates a satisfying assignment against every saved clause and XOR row. The [curve-law replay](control_replay_result.json) checks the full 12-position relation on the frozen public point independently. The [terminal audit](terminal_audit.json) rebuilds the exact 7,468,648-byte XCNF, checks its SHA-256, validates compressed log hashes and phase sums, and compares the two formulas on the same target. The positive assignment is a known-witness correctness control; its count does not estimate ordinary-query relation yield.

The next experiment is to port the source-aware representation to the frozen N131 W15 source law and first measure complete construction size and witness assignment under its 600-second, 4 GiB boundary. Public N131 search should follow only if the complete formula meets that gate. A useful subsequent algorithmic step is an exact target-conditioned constraint that prunes entire incompatible partial-sum families while retaining every valid decomposition; the present compiler primarily lowers the cost of representing the quartic constraints.

Reproduce the independent archive audit with `python3 experiments/ecc2k130-ic-goal-20260929/n41_basis_aware_quartic_20261011/verify.py`. The run and arithmetic-control entry points are in [run.py](run.py) and [arith_replay.py](arith_replay.py).
