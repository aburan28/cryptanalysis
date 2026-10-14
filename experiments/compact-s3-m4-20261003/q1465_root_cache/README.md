# Q1465: cache exact roots across nested four-summand SAT states

Q1465 keeps Q1464's target-linked chained-`S3` CaDiCaL solver, frozen CNFs,
public targets, leaf decision order, 250,000 pair-candidate cap, one-million
conflict cap, and 60-second native wall cap. It memoizes the exact roots of
`S3(a,b,m)` under the symmetric x-input key `{a,b}`. The cache is shared by
the left pair, right pair, and final target link, and holds at most 2,000,000
entries. A miss uses Q1458's batched-root oracle. The [protocol](protocol.json)
was committed before the ordinary cells. This is proposal `Q1465`,
`PDP4hybrid`, `candidate_id: null`, `run_id: null`, and `isogeny: "none"`.

The frozen N53 curve is `EC1N53Ckb1hf77aab617904`, with normal-basis
weight bound 4, `B=324,042` actual usable base points, and `K=3,057` folded
columns. N83 is `EC1N83Ckb1h876c2921cb64`, weight bound 6,
`B=408,131,750`, and `K=2,458,625`. Their enumerated-set digests,
public targets, and workload IDs are in the protocol and run receipts.
No isogeny transport is used.

## Correctness and ordinary result

The [planted controls](control_result.json) recover independently verified
four-point relations at both degrees. Their retained native joint snapshots
are independently checked by the Q1455 Python oracle. The
[archive verifier](verification.json) checks the frozen inputs, reports,
cache-accounting identities, receipts, and small snapshots. Q1465's ordinary
rejection snapshots exactly equal Q1464's on all three cells; Q1464's
separate serial-root audit therefore also covers the first large ordinary
snapshot at each degree. It does not cover every large rejection.

| Input | Q1464 / Q1465 exact checks | Q1464 / Q1465 actual root evaluations | Q1465 field mul / sqr / inv | Q1465 peak child RSS | Verified relations |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 known-satisfiable selected preimage | 4 / 4 | 403,399 / 195,344 | 3,201,703 / 14,202,706 / 33,229 | 442,580,992 bytes | 0 |
| N53 ordinary full target | 4 / 4 | 403,399 / 195,344 | 3,201,674 / 14,202,542 / 33,227 | 471,187,456 bytes | 0 |
| N83 ordinary full target | 2 / 2 | 998,801 / 493,161 | 7,837,487 / 51,404,310 / 60,326 | 824,754,176 bytes | 0 |

All three solver cells reached the 60-second native cap. The cached N83
run used more memory than Q1464's 336,756,736-byte peak, and its total
field inversions increased from 29,430 to 60,326 as the SAT paths diverged.
The exact root-evaluation reduction is an algorithmic count on identical
checked snapshots. Wall and full-operation comparisons are exploratory on
an unisolated host; they do not establish an end-to-end speedup.

The ordinary cells still have zero verified relations and no novel matrix
rows. Their work is charged as failed search. Natural useful-row yield,
successful PDP cost, and complete N131 `2^x` remain unknown. The
`2^61` challenge gate remains closed. This result makes root recomputation
a smaller share of the bottleneck; the next solver must construct
target-linked chains in broader domains rather than wait for the same
bounded late-state rejections.

Reproduce the archive checks with the accepted Sage launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1465_root_cache/build.py --check
python3 experiments/compact-s3-m4-20261003/q1465_root_cache/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1465_root_cache/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1465_root_cache/verify_archive.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```
