# Q1464: widen the exact chained-S3 joint check to 250,000 pairs

Q1464 changes only the per-pair candidate cap in Q1458's batched-root
CaDiCaL propagator from 4,096 to 250,000. It reuses the same three frozen
CNFs, public targets, leaf decision order, one-million conflict cap, and
60-second native wall cap. A partial state is checked only when **both**
pair candidate products fit within the cap. The rule enumerates each
pair's exact `S3` midpoint x roots and tests the target-linked final
`S3` equation; a no-chain result emits a clause guarded by the target
selector and assigned leaf bits. This remains proposal `Q1464`, with
`candidate_id: null`, `run_id: null`, `isogeny: "none"`, and `PDP4hybrid`.

The [protocol](protocol.json) and implementation were committed before
the ordinary cells. They pin N53 curve `EC1N53Ckb1hf77aab617904`, W≤4,
actual usable base `B=324,042`, folded columns `K=3,057`; and N83 curve
`EC1N83Ckb1h876c2921cb64`, W≤6, `B=408,131,750`, `K=2,458,625`.
The complete enumerated-set digests and frozen workload IDs are in the
protocol and receipts. The [planted controls](control_result.json) both
return independently verified four-point relations, and independently
replay all their retained native join snapshots.

## Ordinary and unpinned result

The [archive audit](verification.json) checks all three receipts, exact
input archives, stage outputs, model status, and operation counts. Every
cell reached its native wall cap with no SAT model or verified relation.
Failed search work is included. The machine has no CPU-isolation receipt,
so wall times and memory differences are exploratory stage diagnostics,
not controlled speedups.

| Input | Q1458 checks at cap 4,096 | Q1464 checks / no-chain rejections | Q1464 pair-root calls | Q1464 field mul / sqr / inv | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 known-satisfiable unpinned slice | 2 | 4 / 4 | 333,181 | 6,111,477 / 26,466,880 / 33,245 | 338,460,672 bytes |
| N53 ordinary full target | 2 | 4 / 4 | 333,181 | 6,111,477 / 26,466,880 / 33,245 | 444,497,920 bytes |
| N83 ordinary full target | 1 | 2 / 2 | 749,157 | 14,433,893 / 92,467,946 / 29,430 | 336,756,736 bytes |

The first N53 ordinary rejection had 67,677 leaf-pair candidates on each
side; the first N83 rejection had 249,719 on each side. Both are beyond
Q1458's cap. Q1464 reaches more exact checks on the same inputs and under
the same native wall limit, but the search paths diverge after those
clauses. The zero verified-relation outcome gives no natural useful-row
rate, cost per successful decomposition, or N53-to-N83 solve-growth fit.

## Separate post-result audit of wide rejections

The primary archive verifier independently replays the planted controls
and checks all ordinary receipts, but its Python join does not replay
the large ordinary rejection snapshots. After seeing the ordinary results,
we froze a separate [serial-root audit protocol](serial_audit_protocol.json)
selecting the **first** retained ordinary no-chain state at each degree.
The [serial audit](serial_audit.cpp) uses Q1420's separate per-pair root
oracle, without Q1458's batched-root code. The two [audit runs](serial_audit_runs)
completed with zero x-only target chains:

| Selected ordinary state | Pair candidates per side | Distinct midpoint x values per side | Serial root calls | X-only chains |
| --- | ---: | ---: | ---: | ---: |
| N53 | 67,677 | 66,367 | 201,721 | 0 |
| N83 | 249,719 | 246,523 | 745,961 | 0 |

This establishes exact x-only infeasibility for those two selected fixed
states. It does not independently replay every Q1464 rejection, measure
natural relation yield, or prove the solver is fast enough for N131.
The complete N131 `2^x` remains unknown and challenge dispatch stays
closed.

Reproduce with the checked Sage launcher for every Sage job:

```sh
python3 experiments/compact-s3-m4-20261003/q1464_joint_cap250k/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1464_joint_cap250k/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1464_joint_cap250k/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/q1464_joint_cap250k/serial_audit_protocol.py --check
```
