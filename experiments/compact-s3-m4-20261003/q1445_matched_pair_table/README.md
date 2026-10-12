# Q1445: pair-table control on the exact Q1438 bases

Q1445 puts a signed-Frobenius pair-sum table on the **same curves, factor
bases, and ordinary public targets** used by the Q1444 compact-`S3` SAT
cells. It is a matched-input stage control, not a new target-guided
decomposition method or a complete index-calculus candidate. The two
methods have different query laws and preparation costs, so their exploratory
wall times are not a controlled CPU speed ratio.

The [frozen protocol](protocol.json) was committed before either ordinary
query ran. It records the exact curve IDs, usable point counts `B`, folded
columns `K`, base digests, target points, seeds, sample caps, source and input
hashes, accepted Sage runtime, and run order. This remains proposal `Q1445`
with `candidate_id: null`, `run_id: null`, and `isogeny: "none"`. `PDP4mitm`
names the four-point pair-table stage; no `IC1` name is assigned until the
whole IC pipeline is specified.

N53 uses `EC1N53Ckb1hf77aab617904`, W≤4, actual `B=324,042`, and
`K=3,057`. The complete point set was materialized once from Q1438's
enumerated orbit representatives, and its digest and distinctness were
checked. N83 uses `EC1N83Ckb1h876c2921cb64`, W≤6, actual
`B=408,131,750`, and `K=2,458,625`. It samples uniformly from **all**
nonzero W≤6 normal-basis x masks: choose a weight in proportion to its
binomial count, draw a support uniformly, reject nonrational or identity
projections, and choose the sign uniformly. Q1438's exact no-collision,
full-orbit receipt makes the accepted projected points uniform over its
complete point base. This avoids replacing the large N83 base with a cached
subset.

The [pre-run controls](validation.json) replay Q1439's archived N53
four-point relation, exercise a synthetic quotient collision with Frobenius
shift 7 and negative sign, and reconstruct 64 sampled N83 projected points
from their sparse-x certificates. These controls were run before the
ordinary queries and do not contribute a natural-yield estimate.

## Frozen ordinary results

| Degree | Table preparation | Target-dependent query | Status | Independently verified relations |
| --- | ---: | ---: | --- | ---: |
| N53 | 500,000 pair samples; 43.188 s | 54,545 pair samples; 6.748 s | four-point relation | 1 |
| N83 | 10,000 pair samples; 9.582 s | 10,000 pair samples; 10.032 s | sample cap; zero key hits | 0 |

The [archive audit](verification.json) independently replays the N53
collision, exact point-base membership, subgroup membership, public target
sum, and four distinct folded columns. The N83 row preserves the zero-hit
sample cap. Both rows record target-independent base loading, table build,
sampler draws and rejections, target-dependent query time, and peak RSS in
their individual [N53](runs/n53_ordinary.json) and
[N83](runs/n83_ordinary.json) receipts. The work unit here is a pair sample
or raw sparse-x draw, not a calibrated field operation. The main search loops
make 609,090 N53 and 30,000 N83 point-add calls; this count excludes base
generation, subgroup checks, and replay. N83's two samplers make 80,079
raw sparse-x draws to obtain 40,000 usable points. Wall times are
exploratory because this host has no CPU isolation receipt.

One successful N53 query does not measure population relation yield or cost
per novel matrix row. The N83 cap provides no successful-cost observation.
There is no N53-to-N83 successful-solve growth fit, no complete degree-131
`2^x`, and no challenge permission. Q1443's target-oblivious first-pair
bound still excludes this search family from the proposed sub-`2^61` N131
path in its declared abstract trial unit. The next solver must use the
public target to constrain **both** sparse pairs before enumerating a first
pair.

## Reproduction

Use the checked repository Sage launcher for every Sage job. To replay the
frozen inputs and receipts without overwriting them:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1445_matched_pair_table/build_n53_base.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1445_matched_pair_table/validate_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1445_matched_pair_table/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1445_matched_pair_table/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The measured runner refuses to overwrite existing receipts. A fresh
checkout can reproduce the ordinary cells in the protocol's run order with
`pair_probe.py --degree 53` and `pair_probe.py --degree 83`, after saving a
checked `sage --runtime-info` receipt and freezing the same inputs. Repeated
wall times require an isolated benchmark receipt before they support a CPU
speedup claim.
