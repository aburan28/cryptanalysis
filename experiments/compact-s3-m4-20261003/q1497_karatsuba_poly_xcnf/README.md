# Q1497: Karatsuba field products in the compact three-S3 XCNF

Q1497 changes the arithmetic circuit in Q1494/Q1496's four-summand
decomposition stage. It keeps the exact normal-basis leaf-window factor
bases, balanced three-`S3` chain, complete raw target-preimage selectors,
ordinary public points, and first-window/Frobenius rotation rule. Each
field-product operand is mapped through the archived, independently
verified ONB-to-polynomial bridge. A padded Karatsuba convolution is
reduced by the archived sparse irreducible modulus, then mapped back to
ONB through native XOR rows. The polynomial basis is an **internal
implementation basis**, not a new curve or isogeny.

The [design](design_protocol.json) was committed and pushed at `421a2fdb`.
The [source-bound protocol](protocol.json), checked [Sage runtime](sage_runtime_info.json),
and arithmetic [validation](circuit_validation.json) were frozen and
pushed at `1a1296dc` before any full solver cell. Q1497 remains a `Q`
proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. It uses the existing `PDP4sat` stage code. Its exact
curve identities and factor-base counts are:

| Degree | Curve ID | Actual usable points `B` | Folded columns `K` | Set SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 430,360 | 4,060 | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 348,006,384 | 2,096,424 | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

## Arithmetic correctness and formula size

For each degree, the validation compares **every** basis-pair product
and 128 seeded arbitrary products with the original ONB multiplier. Two
pinned XCNF multiplication cases per degree return SAT for the correct
answer and UNSAT when one output bit is inverted. The full N53 ordinary
witness and N83 planted four-point control then return SAT; their models
satisfy every XOR row and CNF clause and replay the original public
target with four distinct folded columns.

| Formula | AND gates | Variables | CNF clauses | XOR rows |
| --- | ---: | ---: | ---: | ---: |
| Q1496 N53 ordinary, schoolbook ONB | 25,281 | 26,510 | 106,889 | 795 |
| Q1497 N53 ordinary, Karatsuba | **5,877** | 18,860 | 48,677 | 12,549 |
| Q1496 N83 ordinary, schoolbook ONB | 62,001 | 63,913 | 206,265 | 1,245 |
| Q1497 N83 ordinary, Karatsuba | **15,498** | 48,406 | 66,756 | 32,241 |

The Q1496 AND counts were recomputed from its frozen formula builder; its
run receipts did not retain that count. Exact Q1497 counts come from the
frozen formula builder and run receipts. Fewer AND gates and clauses create
many more XOR rows;
formula size alone cannot establish faster decomposition.

## Frozen solver results

All unpinned cells reached the 60-second CryptoMiniSat cap without a
model. The N53 rotation-44 target is known satisfiable from Q1490, and
the N83 planted target is known representable; their pinned controls
pass. The ordinary rotation-zero N53/N83 cases are matched to Q1496 on
the same curve, factor base, and public target. The [audit](archive_audit.json)
preserves every row, raw logs, source and input hashes, exact conflict and
decision counts, charged stage intervals, and memory.

| Cell | Outcome | Charged target-dependent stage, exploratory | Exact conflicts | Propagations as printed | Peak child RSS, Darwin bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 rotation 44, witness pinned | verified four-point control | 0.332 s | 0 | 2 | 10,895,360 |
| N83 planted, witness pinned | verified four-point control | 1.339 s | 0 | 83 | 15,351,808 |
| N53 rotation 44, all witness bits free | capped, no model | 61.102 s | 397,825 | 98M | 128,483,328 |
| N53 rotation 0, ordinary | capped, no model | 61.075 s | 384,960 | 97M | 120,635,392 |
| N83 planted, witness bits free | capped, no model | 62.178 s | 153,091 | 76M | 235,454,464 |
| N83 rotation 0, ordinary | capped, no model | 62.285 s | 141,056 | 72M | 236,355,584 |

The solver's rounded `M` propagation displays are not exact operation
counts. These wall times lack a host-isolation receipt and are exploratory.
Q1496 processed 337,858 conflicts in its N53 ordinary cell and 165,889
in N83 ordinary at the same cap; these are different circuits, and neither
returned a relation, so no speed ratio or cost per relation follows.

The Q1497 XOR components exceeded the **512-row** Gaussian limit inherited
from Q1496. CryptoMiniSat logged zero active matrices initially in every
unpinned cell and explicit "too many rows" rejections, including a
4,624-by-4,730 component at N53 and a 12,137-by-12,303 component at N83.
Q1497 therefore measures a smaller nonlinear circuit under those frozen
limits, not the same active-Gauss regime as Q1496. A separate matched
row-limit experiment is needed before attributing a result to Karatsuba
with Gaussian elimination.

There is still no successful unpinned N83 PDP cost, ordinary relation
yield, novel rank, complete N131 `2^x`, or sub-`2^61` claim. The challenge
gate remains closed.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/validate_circuit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n53_known_rotation_44 --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n83_planted_rotation_0 --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n53_known_rotation_44 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n53_ordinary_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n83_planted_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/run.py --cell n83_ordinary_rotation_0 --check
python3 experiments/compact-s3-m4-20261003/q1497_karatsuba_poly_xcnf/audit.py --check
```
