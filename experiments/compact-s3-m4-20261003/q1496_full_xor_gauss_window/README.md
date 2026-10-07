# Q1496: bounded Gaussian elimination on the full window S3 system

Q1494 submitted all three chained `S3` links as native XOR rows, but its
default CryptoMiniSat settings excluded the large field-product matrices.
Q1496 changes **only** four Gaussian settings on Q1494's byte-identical
XCNF cells: `--maxmatrixcols 24576 --maxmatrixrows 512
--maxnummatrices 8 --autodisablegauss 0`. The same single-thread binary,
60-second ordinary cap and one-million-conflict cap are used. This tests
whether admitting the rejected XOR components changes bounded search.

The [design](design_protocol.json) was committed at `d3847357`, and the
[source-bound protocol](protocol.json) was frozen at `db2b4059`, both before
the runs. The protocol hashes the checked [Sage runtime](sage_runtime_info.json),
CryptoMiniSat binary, Q1494 runner, exact parent receipts, and Q1496 source.
Q1496 is a stage proposal: `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. It does not claim a complete index-calculus candidate.

| Degree | Exact curve ID | Actual usable base points `B` | Folded columns `K` | Base set SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 430,360 | 4,060 | `42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 348,006,384 | 2,096,424 | `f2d7771988cbd03fa4ea3145fc3870e5a3fc44171b9a57165257f016cdeb19d4` |

## Frozen results

The 327-bit pinned N53 control returns SAT and independently replays a
four-point relation on the original public target. It is a correctness
control, not a measured unpinned solve. All three unpinned cases return
`INDETERMINATE` at the time cap, including the N53 rotation-44 case whose
relation is known from Q1490. The [independent audit](archive_audit.json)
checks all four rows, exact input equality to Q1494, source and log hashes,
timing sums, native statuses, and large-matrix activation. The Sage
`--check` commands below rebuild the formulas and replay any SAT model.

| Cell | Q1494 default matrices / conflicts | Q1496 initial matrices / largest accepted | Q1496 exact conflicts | Charged Q1496 target stage | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| N53 rotation 44, pinned control | 0 / 0 | solver finished before matrix initialization | 0 | 0.218 s | verified relation |
| N53 rotation 44, unpinned known satisfiable | 0 / 548,781 | 3 / 8,586 columns | 341,697 | 60.945 s | cap, no model |
| N53 rotation 0, ordinary | 0 / 545,528 | 3 / 8,586 columns | 337,858 | 61.143 s | cap, no model |
| N83 rotation 0, ordinary | initially 0 / 279,237 | 3 / 20,916 columns | 165,889 | 61.896 s | cap, no model |

The N53 unpinned formula has 26,510 variables, 106,889 CNF clauses, and
795 XOR rows; N83 has 63,913 variables, 206,265 clauses, and 1,245 XOR
rows. Each Q1496 formula SHA-256 matches its Q1494 parent receipt exactly.
No unpinned run emitted a model. Their logs have no "too many columns"
rejection, and the solver footer records active Gaussian matrices. In the
ordinary N53 cell, a 212-by-6,519 matrix reports 3,097K truth-finding
checks with nonzero propagation and conflict percentages. In ordinary N83,
the 332-by-15,936 matrix reports 1,409K such checks. Thus this is an
actual Gaussian search comparison, rather than just a command-line flag
change.

At roughly the same 60-second cap, Q1496 processes fewer conflicts than
Q1494 while using more peak memory: 199,835,648 versus 156,549,120 Darwin
bytes for ordinary N53, and 286,621,696 versus 196,165,632 for ordinary
N83. Conflict counts are algorithm-specific search events; fewer conflicts
at a fixed cap do not show that the remaining search is closer to a
solution. CryptoMiniSat prints propagations rounded as `K` or `M`; the
[receipts](runs/) preserve those raw displays and exact conflicts and
decisions. CPU wall times are exploratory without host isolation.

This closes the specific Q1494 configuration gap. It provides no
successful unpinned PDP cost, ordinary relation-yield estimate, novel
matrix rank, complete N131 `2^x`, or sub-`2^61` claim. The challenge gate
remains closed.

## Next gate

The next solver candidate should change the **search structure**, with
all four leaves and both pair midpoints free. A target-aware compressed
pair-support join across many cyclic windows is a concrete direction: it
must avoid both Q1488's full pair table and the narrow single-midpoint
domains in Q1485–Q1487. First require unpinned recovery and independent
replay of Q1490's known ordinary N53 relation, counting complete
target-dependent work. Then require a known-representable N83 control and
ordinary N83 attempts under frozen caps. A capped failure stays a failure
row. Only verified unpinned successes across a frozen ordinary-query panel
could support cost-per-relation and natural-yield estimates; a complete
N131 work exponent additionally requires rank, final matrix, and target
recovery costs.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/run.py --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/run.py --cell n53_known_rotation_44 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/run.py --cell n53_ordinary_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/run.py --cell n83_ordinary_rotation_0 --check
python3 experiments/compact-s3-m4-20261003/q1496_full_xor_gauss_window/audit.py --check
```
