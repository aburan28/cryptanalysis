# Q1471: wider exact joint-chain admission on N83

Q1471 raises only the pair-domain admission cap of Q1467's compact
four-summand chained-\(S_3\) solver, from 250,000 to 1,000,000 pair
candidates on each side of the target-coupled join. It reuses the same
native binary, materialized CNFs, decision policy, curve, factor base,
workload IDs, and public targets. The exact curve is
`EC1N83Ckb1h876c2921cb64`; the W≤4 base has 1,934,066 usable subgroup
points, 11,651 folded signed-Frobenius columns, and digest
`1b4110f055c88a4b1be2bfdd4bdb1cfca62bc41f49f0a5cac7698f7d4fc35325`.
The [protocol](protocol.json) was committed before either run and retains
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`. This is a
`PDP4hybrid` stage test, not a complete IC candidate.

The planted public target is known representable because Q1467's fully
pinned version independently recovered a four-point relation on it. Its
Q1470 unpinned run still had no model after 600 seconds at the old cap.
The ordinary target is exactly Q1467's frozen ordinary public point. Both
Q1471 cells use a 120-second native wall cap and preserve all failed work.

| Exact N83 input | Native status | Exact joint checks | Cap skips | SAT conflicts | Field mul / sqr / inv calls | Peak child RSS on Darwin |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Known-representable, leaves unpinned | censored at wall cap | 3 | 298 | 89,132 | 19,869,450 / 129,227,176 / 87,401 | 1,576,255,488 B |
| Ordinary, leaves unpinned | censored at wall cap | 3 | 323 | 90,177 | 19,072,905 / 122,700,646 / 36,011 | 701,874,176 B |

The source-bound [audit](archive_audit.json) checks both receipts, the
binary and input hashes, native counters, matched prior target/base records,
and the known-solution control. No model or verified relation was returned.
The wider cap admitted two additional exact checks per cell versus the
Q1467 250,000-cap runs, but most partial states still exceeded the new
cap. It increased arithmetic work substantially without producing an N83
successful-solve cost or natural relation. The ordinary run is one censored
query, so natural yield and cost per useful N83 row remain unknown. Wall
times are exploratory because the host was not isolated.

At N131, this cap experiment supplies no complete `2^x`: factor-base
construction, successful relation collection, late-rank behavior, matrix
build and solve, target descent, and scalar replay still need measured or
bounded costs. The challenge stays closed. The next solver change should
constrain both pairs earlier than this exact-join admission point, or
measure a successful unpinned N83 witness on the same frozen base.

## Reproduce the audit

```sh
python3 experiments/compact-s3-m4-20261003/q1471_n83_wide_join/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1471_n83_wide_join/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The [runner](run.py) refuses to overwrite results. All new local Sage jobs
use the repository's checked launcher.
