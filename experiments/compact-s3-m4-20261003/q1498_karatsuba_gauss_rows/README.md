# Q1498: active Gaussian elimination on Q1497's Karatsuba XCNF

Q1497 reduced the nonlinear field-product circuit but its many native
XOR rows formed matrices larger than CryptoMiniSat's frozen 512-row
limit. Q1498 reruns **byte-identical** Q1497 XCNFs with only
`--maxmatrixrows` changed from `512` to `16384`. The same CryptoMiniSat
5.14.7 binary, single thread, 60-second unpinned cap, conflict cap,
curves, exact factor bases, public targets and pinned controls remain.

The [design](design_protocol.json) was committed and pushed at `b14a1476`.
The [protocol](protocol.json) bound Q1497's exact six formula receipts,
source, checked [Sage runtime](sage_runtime_info.json), solver binary, and
new options at `f85cbc3f` before running any cell. Q1498 remains a stage
proposal: `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`.

| Degree | Exact curve ID | Actual usable base points `B` | Folded columns `K` |
| ---: | --- | ---: | ---: |
| 53 | `EC1N53Ckb1hf77aab617904` | 430,360 | 4,060 |
| 83 | `EC1N83Ckb1h876c2921cb64` | 348,006,384 | 2,096,424 |

## Frozen results

Both pinned full-chain controls again return SAT and independently replay
four distinct folded columns summing to their public targets. Every
unpinned cell returns `INDETERMINATE` at the time cap. The
[independent audit](archive_audit.json) checks the exact Q1497 formula
hash for each matched cell, the one-option change, source and output
hashes, raw statuses and counters, charged phase sums, and the solver's
Gaussian activity footer. The Sage `--check` commands below rebuild the
formulas and replay any model.

| Cell | Q1497 conflicts, zero initial matrices | Q1498 initial matrices / largest accepted | Q1498 conflicts | Charged Q1498 stage, exploratory | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| N53 rotation 44, known satisfiable | 397,825 | 7 / 4,730 columns | 181,483 | 60.806 s | cap, no model |
| N53 rotation 0, ordinary | 384,960 | 7 / 4,730 columns | 169,987 | 60.971 s | cap, no model |
| N83 planted, known representable | 153,091 | 6 / 12,303 columns | 35,256 | 62.288 s | cap, no model |
| N83 rotation 0, ordinary | 141,056 | 7 / 12,303 columns | 40,123 | 61.806 s | cap, no model |

The N53 ordinary solver footer records nonzero Gaussian checks and
propagation on a 3,924-by-4,030 matrix; N83 ordinary records the same on
the 12,137-by-12,303 matrix. There are no matrix row or column rejections
in Q1498's unpinned logs. This confirms **active** Gaussian reasoning on
the components rejected in Q1497. Q1498 used more memory: ordinary N53
peak child RSS rose from 120,635,392 to 257,064,960 Darwin bytes;
ordinary N83 from 236,355,584 to 576,077,824 bytes. Fewer conflicts
within a fixed cap do not show progress toward a relation, and the
single-host wall times are exploratory without CPU isolation.

This closes the Karatsuba matrix-admission configuration gap. Neither
Q1497 nor Q1498 measured a successful unpinned four-point decomposition
at N53 or N83. Their capped prefixes cannot establish natural relation
yield, cost per useful row, novel rank, final-matrix work, target recovery,
or a complete N131 `2^x`. The sub-`2^61` challenge gate stays closed.

## Reproduce custody checks

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n53_known_rotation_44 --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n83_planted_rotation_0 --control --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n53_known_rotation_44 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n53_ordinary_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n83_planted_rotation_0 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/run.py --cell n83_ordinary_rotation_0 --check
python3 experiments/compact-s3-m4-20261003/q1498_karatsuba_gauss_rows/audit.py --check
```
