# Q1478: same-point N53 Pollard-rho reference

Q1478 supplies the missing **one-target rho reference** for Q1477's exact
public point. It is a single-worker distinguished-point walk with 16
partitions and no cross-target state. The [design](design_protocol.json) was
published before the run. The [frozen protocol](protocol.json) pins the
curve, Q1477 target/workload, checked Sage runtime, native source and binary,
walk policy, seed, and limits. It uses curve
`EC1N53Ckb1hf77aab617904`, workload `a4f7b6242393`, and rho reference
`RHO1N53Ckb1h19e1c424260d`. This is not an `IC1` candidate and has
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`.

The [run receipt](runs/primary/receipt.json) records **10,732,337 walk
steps** across **10,281 walks**. It retained 10,279 distinguished points,
found one nondegenerate endpoint collision, and independently replayed the
recovered scalar **7,916,229,610,986** to the frozen public point. The
[checked Sage audit](audit_result.json) reconstructs both collision states
from their coefficients, verifies the collision equation modulo the exact
prime subgroup order, replays three complete walk prefixes with a separate
group implementation, and checks the Q1477 fixture scalar. The
[small-prime control](control_result.json) verifies 6,560 collision equations
before the measured run.

| Exclusive target-dependent phase | Native wall | Field mul | Field sqr | Field inv |
| --- | ---: | ---: | ---: | ---: |
| Target and subgroup validation | 0.000406 s | 1,304 | 6,982 | 130 |
| Target-dependent jump precomputation | 0.006062 s | 20,410 | 109,522 | 2,041 |
| Walks, failed starts, table and collision recovery | 38.417190 s | 120,439,230 | 639,198,190 | 12,043,923 |
| Scalar replay | 0.000198 s | 630 | 3,381 | 63 |
| **One-target online total** | **38.423855 s** | **120,461,574** | **639,318,075** | **12,046,157** |

All four phase clocks sum exactly to the online interval, which begins
before target-dependent validation and stops after scalar replay. The run
also counted 11,195,006 point additions and 871,750 doublings across all
phases. Peak child RSS was 4,718,592 bytes. The external process interval
was 38.823 seconds, including launch and input decoding. The
[raw transcript](runs/primary/stdout.json) preserves every completed walk,
step count, endpoint status, phase cost, and the collision certificate.

The Q1477 paired IC comparator has a 45.688-second **query-through-replay**
interval on this same point, but its pre-clock target subgroup check was not
separately timed. The strict IC online total and therefore the primary
`rho_online_ms / IC_online_ms` remain `null`. Both wall intervals are
exploratory because the host lacks an isolation receipt. One rho run also
does not characterize its run-to-run variance. This walk does not fold the
Frobenius automorphism, so it is a specified same-point reference rather
than an optimized ECC2K rho floor. This result supplies no
successful N83 compact decomposition or complete N131 `2^x`; the challenge
gate remains closed.

## Reproduce the archived checks

```sh
python3 experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/build.py --check
python3 experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/control.py --check
python3 experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

These checks replay custody and mathematical evidence; they do not rerun
the rho walk.
