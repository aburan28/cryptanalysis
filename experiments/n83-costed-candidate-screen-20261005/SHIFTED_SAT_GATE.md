# N83 shifted S3 correctness, bounded SAT, and Hamming transfer gate

This follows the [shifted S3 encoding gate](SHIFTED_S3_ENCODING_GATE.md) on
`EC1N83Ckb1h2bcb59d56ad6`, with subgroup order
`r = 2417851639230796216685689` and cofactor four. The
[frozen protocol](shifted_sat_protocol.json), [18-branch ledger](sat_panel.json),
and [branch table](SAT_PANEL.md) preserve the exact public target, geometry,
solver digest, caps, failures, and per-attempt receipts. These are proposal
stage diagnostics with `candidate_id: null`, not complete IC runs.

## Correctness controls

Two planted targets were built from local private witnesses. The witnesses
remain untracked; the committed public fixtures expose only target points,
raw fibers, and witness commitments. The [integer-field replay](replay_shifted_sat_fixture.py)
independently checked every exact shifted slot mask, point lift, cofactor-four
projection, subgroup membership, measured factor-base orbit, nonidentity
prefix, S3 link, raw fiber, and target. Both fixtures passed.

The fully pinned S3 circuits solved under the frozen envelope. Their SAT
models satisfy every CNF and XOR row, have an exact raw-fiber group lift in
the measured base, and pass a separate [installed-Sage replay](sage_replay_shifted_sat_model.py).
The measured solver times, about 0.455 s for `m=7,d=12` and 0.430 s for
`m=8,d=11`, are **pinned correctness controls**, not estimates for ordinary
queries. They fixed every factor mask and intermediate x coordinate.

The [small-field control](sage_small_shifted_s3_control.py) exhaustively
compared S3-chain target-x sets with group-sum target-x sets for the frozen
shifted-slot rule:

| Field | Arity | Labeled rational x tuples | False target-x pairs | Missed target-x pairs | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `2^3` | 7 | 0 | — | — | Vacuous: all slots have no rational x |
| `2^3` | 8 | 0 | — | — | Vacuous: all slots have no rational x |
| `2^4` | 7 | 128 | 0 | 0 | Pass on this complete small-field grid |
| `2^4` | 8 | 256 | 0 | 0 | Pass on this complete small-field grid |

The first degree-3 run failed an assertion that every slot is nonempty; its
[failure receipt](runs/small_shifted_n3_m7_v1/failure.json) is retained. The
corrected v3 degree-3 reports mark full-locus equivalence `null`, not true.
Small-field agreement does not prove N83 ordinary-query coverage or exclude
all possible exceptional-chain behavior on larger fields.

## Frozen N83 SAT panel

For each geometry, one fully pinned planted branch and all four unpinned
fibers of each of the planted and previously frozen ordinary public targets
were attempted. CryptoMiniSat used one thread, an internal 30-second and
200,000-conflict cap, and a **45-second outer process-tree wall cap** with
a **2 GiB RSS cap**. The checked Sage launcher saved `--runtime-info` before
each branch. Branches ran in the frozen order; all raw outcomes are in the
machine ledger, including outer-guard failures with no inner receipt.

| Geometry | Actual `B` per slot | Folded `K` | Pinned planted | Four unpinned planted fibers | Four ordinary fibers | Ordinary verified relations |
| --- | ---: | ---: | --- | --- | --- | ---: |
| `m=7,d=12` | 4,036 | 1,018 | SAT, Sage replay pass | 4 outer wall caps | 4 outer wall caps | 0 |
| `m=8,d=11` | 2,018 | 501 | SAT, Sage replay pass | 4 outer wall caps | 4 outer wall caps | 0 |

Every unpinned branch serialized its XCNF and ran the solver before reaching
the outer cap. No unpinned SAT model, UNSAT proof, or verified group relation
was returned under this envelope. The seven-summand pinned XCNF has 148,397
variables and 431,020 clauses including pins; the eight-summand version has
171,204 variables and 497,220 clauses. The earlier unpinned encoding sizes
are recorded separately in the encoding gate. The sum of four ordinary
process envelopes is about 180.8 s per geometry, but includes repeated
launch and startup. It is **supplementary**, not the one-target online time.

The four fibers are correlated alternatives for **one** ordinary target,
not four independent targets. Therefore 0/4 under this cap is a bounded
zero-yield cell, not a confidence interval or an estimate of the natural
relation rate. Since even unpinned planted recovery did not finish, this SAT
formulation has not passed its witness-search promotion gate.

## Exact Hamming-ideal transfer screen

[La Scala, Marchesin, and Tiwari](https://arxiv.org/html/2609.18866) derive
exact-weight Hamming ideals and degree-bounded lifted forms; their MultiSolve
analysis is presented for polynomial systems with at most one solution.
The shifted-slot candidates here allow **all nonzero** slot masks. Imposing
weight 3 or 4 is therefore a different factor-base policy, not an equivalent
encoding of either unrestricted shifted candidate. The
[checked-Sage screen](sage_hamming_transfer_screen.py) enumerated every
weight-3-or-4 mask in every slot, projected both point lifts, removed identity
images, and verified every signed-Frobenius orbit against the measured base.

| Shifted geometry | Masks per slot | Restricted usable `B` per slot | Restricted union `B` | Folded `K` | Exact ordered tuples / `r` | Ratio to unrestricted tuple count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `m=7,d=12` | 715 | 710 | 4,970 | 108 | 0.0000376165353 | 0.00000521375 |
| `m=8,d=11` | 495 | 492 | 3,936 | 76 | 0.00142000925 | 0.0000124839 |

For a uniformly chosen subgroup target, the exact average number of ordered
projected-factor tuples is `product(B_slot)/r`. The probability that **any**
tuple reaches that target is at most this average, capped at one. Thus the
two restricted policies have target-support ceilings of about 0.00376% and
0.142%, respectively. These bounds concern uniform targets and this exact
factor-base policy; they do not estimate the yield of the one fixed ordinary
target, SAT solve time, or a guided/nonuniform query law.

Conversely, the unrestricted shifted geometries have exact average ordered
tuple multiplicities 7.215 and 113.747 per uniform subgroup target. Those
counts do not prove the multiplicity of this fixed target, but they show why
the paper's at-most-one-solution premise cannot simply be assumed for the
unrestricted group-decomposition problem. A global W3/W4 factor base with an
alternative FC/QFC Hamming representation is a separate solver proposal;
this screen makes no performance claim for it.

## Charged decision

The [one-target accounting contract](COST_ACCOUNTING.md) requires exclusive
target-query, PDP, relation-check, descent, and recovery-check times, a
verified target scalar, and a same-point verified rho solve. None exists in
this panel. The [ledger](sat_panel.json) leaves all five primary online phase
costs, `T_online,1`, rho online time, speedup, and ordinary-yield uncertainty
`null`. There is no isolated-host timing receipt; all observed CPU wall times
are exploratory. The exact tuple counts are mathematical diagnostics, and
the pinned times are correctness controls.

The current plain S3 SAT route passes construction and pinned replay but
does not produce an unpinned relation at the frozen cap. The tested
weight-3-or-4 restriction sacrifices too much target support to promote as a
drop-in transfer. A next pilot should price a materially different solver,
such as an indexed partial-pair route, including table construction, peak
memory, all four target fibers, failures, verification, rank yield, and
single-target descent. For `m=8,d=11`, the earlier raw one-pair payload model
is 65,157,184 bytes before indexing and allocator overhead; it is only a
conditional design size. No new `IC1` candidate or speedup is promoted here.
