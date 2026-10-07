# Q1483: fixed-window compact S3 search

The [pre-registered design](design_protocol.json) makes one controlled change
to Q1482's exact window-base search: it selects the cyclic window beginning
at position zero for each of the four leaves before SAT search. Every Q1482
planted witness lies in this slice, so the unpinned planted cells have known
solutions. The ordinary N53/N83 public points and target-preimage lists stay
byte-identical to Q1482. The exact Q1481 usable base sizes and set digests
also stay fixed.

This removes uncertainty about window positions from the Boolean search and
allows the native theory to see only `d` free leaf coordinates. It restricts
the accepted relations to one orientation of each leaf. At N131 that is a
small part of the full Frobenius orbit-union base, so even a successful N83
slice cannot be projected as full-base N131 yield or a complete solve.
Q1483 remains a `Q` proposal with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`.

## Frozen result

The design was committed as `7342961b`; `2792ee8a` froze the six exact CNFs,
public targets, planted fixtures, checked Sage runtime, solver binary, source
hashes, and caps before execution. The stage IDs use the **actual** Q1481
usable base counts:

- `PS1N53Ckb1fb430360PDP4hybridh283e31639cd9`
- `PS1N83Ckb1fb348006384PDP4hybridh7037228c0b53`

The first N53 unpinned planted attempt, `R1`, returned from its native
subprocess while the volume was full. Its stdout could not be written, so
its native outcome and operation counts are unknown. Its
[`failure.json`](runs/n53_planted_unpinned/failure.json) and raw CNF remain
in the archive. Commit `81967b57` froze a separate, source-bound `R2` with
the same input, binary and limits before rerunning it. The R1 failure is
**not** reclassified as a timeout or no relation.

The [archive audit](archive_audit.json) rebuilt all six inputs, checked
receipts and file hashes, and independently replayed both pinned SAT models
as four-distinct-column relations on the public points. It also verified the
R1 failure record and the separate R2 custody. All wall times are exploratory
because there is no isolated-host receipt.

| Case | Attempt | Native result | Verified relations | SAT propagations | Field mul calls | Direct right `S3` evaluations |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| N53 planted pinned | R1 | SAT | 1 | 51,147 | 209 | 0 |
| N83 planted pinned | R1 | SAT | 1 | 124,917 | 227 | 0 |
| N53 planted unpinned | R1 | infrastructure error | 0 | unknown | unknown | unknown |
| N53 planted unpinned | R2 | 60 s cap | 0 | 2,171,389 | 573,129,133 | 143,253,504 |
| N83 planted unpinned | R1 | 60 s cap | 0 | 7,400,625 | 334,873,753 | 83,689,472 |
| N53 ordinary | R1 | 60 s cap | 0 | 2,310,103 | 588,202,413 | 147,021,824 |
| N83 ordinary | R1 | 60 s cap | 0 | 7,372,885 | 335,135,897 | 83,755,008 |

The fixed-window clauses reduced the nominal leaf domain, but this native
solver still spent each ordinary prefix evaluating tens or hundreds of
millions of right-pair `S3` conditions without a support. These are censored
prefix costs, not successful-solve costs. No ordinary relation, novel row,
natural yield rate, or complete N131 `2^x` follows from them. The restricted
orientation also cannot be treated as the full Q1481 base at N131.

The next solver gate is an **exact window-aware, target-coupled pair-support
method** that can find a fully unpinned known N83 witness before an ordinary
N83 query. It must expose all counted SAT and field operations and include
failed attempts; changing the decision order alone has not crossed this gate.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1483_fixed_window_s3/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1483_fixed_window_s3/run_recovery.py --freeze
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1483_fixed_window_s3/audit_results.py --check
```
