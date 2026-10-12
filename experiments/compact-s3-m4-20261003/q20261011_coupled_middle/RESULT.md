# Q1439: coupled middle decisions do not improve final-link throughput

The new `seededcoupled` callback chooses the missing middle-row x bits after
the other middle row is complete. On the frozen N83 ordinary public point it
made 145 such decisions and checked 288 complete final links in 136,006
counted field API entries. The matched earlier `seededpos` run checked 1,645
final links in 383,928 entries under the same 30-second, 5,000-conflict and
128-early-state caps: **4,285 versus 2,118 final checks per million entries**.
At N53 the coupled branch made zero decisions and checked zero final links.
The policy is retained as a bounded diagnostic; its final-link throughput is
lower on the N83 point.

N53 is `EC1N53Ckb1hf77aab617904` with actual B=24,062, folded K=227,
and factor-base digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`.
N83 is `EC1N83Ckb1h876c2921cb64` with actual B=30,977,592, folded
K=186,612, and digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Both workloads use the same frozen ordinary public point and
`isogeny: "none"` as Q1437 and Q1438. `Q1439` is a PDP-stage proposal;
`candidate_id` and `run_id` are null.

## Fixed comparison

The Q1439 executable changes only the external decision callback from
Q1437. It keeps `satpivot` S3 roots, `selector` early target support,
`eager` leaf rationality, seed 2 at N53 and seed 8 at N83. Each ordinary run
has a 5,000-conflict and 30-second cap and at most 128 checked early states.
The two previous Q1438 `seededpos` rows have matching input points, seeds,
limits and stage code. CPU timings on this host are exploratory; the
operation and search counters are the algorithmic comparison.

| Field / policy | Status and limit | Coupled decisions | Checked middle row 4 / row 5 | Final-link checks | API entries | Final checks per million entries |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| N53 Q1438 `seededpos` | `BOUNDED_UNKNOWN`; wall | n/a | 0 / 90 | 0 | 4,320,272 | 0 |
| N53 Q1439 `seededcoupled` | `BOUNDED_UNKNOWN`; wall | 0 | 0 / 58 | 0 | 2,784,208 | 0 |
| N83 Q1438 `seededpos` | `BOUNDED_UNKNOWN`; wall | n/a | 0 / 128 | 1,645 | 383,928 | 4,285 |
| N83 Q1439 `seededcoupled` | `BOUNDED_UNKNOWN`; wall | 145 | 0 / 128 | 288 | 136,006 | 2,118 |

All Q1439 middle states had already appeared in the earlier screen/deep
rounds. Including *all* failed and bounded attempts on each same point,
the cumulative charged field API entries are 12,738,135 (\(2^{23.60}\))
at N53 and 2,914,690 (\(2^{21.47}\)) at N83. The distinct checked middle
state counts remain 146 and 206. Successful-query work and relation yield
remain unmeasured, and the N131 fully charged \(2^x\) challenge projection
remains null. The N131 W<=6 necessary affordability ceiling is less than
\(2^{33.36}\) abstract work units per ordinary query under the \(2^{61}\)
total cap; the API-entry unit is not calibrated to it.

`validate.py` passed source, binary, runner, prior-receipt and raw-log hash
checks, all operation sums and cumulative state sets, and 16 independent
leaf-trace decisions. Two locked controls with the new executable passed
independent S3 evaluation. The controls and full measurements are archived.

## Next parameter

The earlier selected N53 seed checked 1,725 final links in the Q1437 run
with early-support cap 8 and a 5-second wall cap. Its Q1438 run with cap 128
and a 30-second wall cap checked zero final links. This cap is the next
hyperparameter to screen at matched budgets. The next run should compare
caps 8, 25 and 128 on the same N53/N83 points, rank by verified final-link
work per field API entry, and keep all screen/deep/coupled costs in the
one-target ledger.

## Reproduction

After preparing the frozen Q1430 CNF/maps and Q1432 target files:

```sh
sh experiments/compact-s3-m4-20261003/q20261011_coupled_middle/build.sh /private/tmp/q1439_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_coupled_middle/run.py --binary /private/tmp/q1439_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_coupled_middle/validate.py --binary /private/tmp/q1439_insearch
```
