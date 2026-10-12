# Q1479: target-conditioned partial midpoint domains

Q1479 tests a necessary target-conditioned rule for the compact four-summand
chained-`S3` solver. Once the first leaf pair has at most 4,096 weight-valid
completions, the native propagator enumerates its possible first midpoints,
maps those through the selected target `S3` link, and restricts the second
midpoint. It rejects an unsupported partial second midpoint or implies bits
shared by every compatible value. Every learned clause is guarded by the
assigned target selector, first-pair leaf bits, and second-midpoint bits. The
domain includes nonrational and otherwise unusable leaf x values, so it is a
sound overapproximation. It does not construct `S5`.

The [design](design_protocol.json) was published in commit `5d11c06f` before
implementation. The [frozen protocol](protocol.json), solver binary, six
unchanged Q1476 inputs, source hashes, checked Sage runtime, and the
small-field control were published in commit `a18ff52a` before the six runs.
The [archive audit](archive_audit.json) checks custody and independently
replays both SAT models. The design is proposal `Q1479`, with `candidate_id`
and `run_id` null and `isogeny: "none"`; it is a point-decomposition stage,
not a complete `IC1` pipeline.

| Degree | Exact curve ID | Actual usable base `B` | Folded columns `K` | Base digest |
| ---: | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 2,756 | 26 | `cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 1,934,066 | 11,651 | `1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325` |

The stage IDs are `PS1N53Ckb1fb2756PDP4hybridh150c321b4c8d` and
`PS1N83Ckb1fb1934066PDP4hybridhc571baafe9f6`. The six run IDs append
their unchanged Q1476 workload ID and `R1` to the respective stage ID.
Inputs, source, binary, runtime, run order, and cap hashes are in the frozen
protocol; the native cap is 60 seconds per case and 1,000,000 SAT conflicts.

## Correctness and measured stage work

An independent exhaustive check over `F_8` evaluated the two `S3`
polynomials directly, covering 4,655 partial-left-pair/target domains and
125,685 guarded partial-midpoint states. It verified 40,588 rejection and
28,578 implication cases without excluding an x-only chain. Both pinned
controls replay as verified four-point public relations. The domain rule is
inactive on those fully pinned leaves; the exhaustive control tests the new
guard logic.

| Frozen case | Status | Verified relations | SAT propagations | Field mul / sqr / inv | `S3` roots | Domain builds / rejections / implications | Exact joint checks |
| --- | --- | ---: | ---: | --- | ---: | --- | ---: |
| N53 sorted pinned control | SAT | 1 | 83,088 | 209 / 1,236 / 18 | 5 | 0 / 0 / 0 | 0 |
| N83 sorted pinned control | SAT | 1 | 443,653 | 227 / 1,926 / 18 | 5 | 0 / 0 / 0 | 0 |
| N53 known-representable full coset | 60 s cap | 0 | 628,631 | 198,644,477 / 836,642,836 / 702 | 14,179,931 | 19 / 6 / 632 | 307 |
| N83 known-representable unpinned | 60 s cap | 0 | 841,175,131 | 1,686,725 / 11,005,762 / 103,914 | 26,079 | 2 / 1 / 2,657 | 0 |
| N53 ordinary | 60 s cap | 0 | 373,362 | 196,128,625 / 826,034,926 / 626 | 14,000,197 | 6 / 5 / 472 | 302 |
| N83 ordinary | 60 s cap | 0 | 844,924,022 | 1,908,296 / 12,262,718 / 115,637 | 28,993 | 2 / 1 / 1,599 | 0 |

The N53 free-leaf cells spend their capped interval on roughly fourteen
million `S3` roots each; the exact joint check now fires 302–307 times and
fills the two-million-entry root cache. For the matched N53 ordinary case,
field multiplications rise from 12,052,776 in Q1476 to 196,128,625 here.
At N83 the new rule does issue guarded implications, but the ordinary case
still reaches the cap after 844,924,022 SAT propagations without a model; no
exact joint check is admitted. These are operation counts at a fixed wall
cap, not successful-solve costs or controlled wall-time speedups. The host
has no isolation receipt.

The four free-leaf cases include a selected/known-representable N53 control,
a planted N83 control, and one ordinary target per degree. All four are
censored with zero verified relations. The controls cannot estimate natural
yield, and one ordinary query per degree cannot estimate yield or rank.
Q1479 supplies neither a successful unpinned N83 cost nor a complete N131
`2^x`; both remain unknown. Under Q1414's stated uniform-query and optimistic
novel-row assumptions for its exact N131 W≤6 base, `2^61` total work would
allow less than `2^33.3554` abstract work units per query even with all other
phases set to zero. That ceiling is not a measured PDP cost and does not
establish a speedup or impossibility.

## Reproduce custody and replay checks

```sh
python3 experiments/compact-s3-m4-20261003/q1479_target_mid_domain/build.py --check
python3 experiments/compact-s3-m4-20261003/q1479_target_mid_domain/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1479_target_mid_domain/validate_domain.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1479_target_mid_domain/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

These commands verify the archived evidence; they do not rerun or overwrite
the native solver cells. Each cell preserves raw stdout/stderr, a receipt,
the source-bound operation counters, exploratory wall interval, child peak
RSS, and any SAT model in `runs/`.
