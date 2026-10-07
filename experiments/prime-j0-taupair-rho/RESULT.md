# Held-out one-target rho gate for gauge-carrying paired τ

The implementation and protocol were committed before target generation.
The fingerprint-checker repair and v3 protocol were frozen in `76027334`;
the new public target was generated and frozen separately in `0c9108e3`
before either solver panel ran. The exact fixture SHA-256 is
`53d2b9075fc0d2179011e4551c37b80cff85f3e2193d1538f574d6f94219d05c`.
The earlier v1 panels and the v2 Release panel remain development evidence:
v1 lacked startup-point fingerprints, and the v2 checker failed while
parsing a hexadecimal fingerprint as decimal. The v2 raw trial results
were preserved, including its checker failure. They were not promoted
after the checker fix.

The held-out workload has one previously unseen public point on
`glv-j0-32`: `(2240586262, 346447426)`. Its independently generated
fixture scalar is `10922529`, and the rho seed is `87869827052049163`.
Each arm received this same point and seed with a fresh rho table. The
serial order was `reference, paired2-free-gauge-batch,
taupair-steered-batch, taupair-steered-batch,
paired2-free-gauge-batch, reference` in each build. All 12 trials
completed, recovered the expected scalar, passed the solver's internal
verification, and passed a separately timed scalar replay. The Release
and UBSan panels both passed their frozen checker gates. Their source,
binary, and fixture hashes, raw stdout/stderr, exact online intervals,
operation counts, and failures are retained in `panel-release.json` and
`panel-ubsan.json`.

| Frozen one-target diagnostic | Free-gauge control | Paired-τ candidate |
| --- | ---: | ---: |
| Nominal startup evaluator field multiplications | 1,383 | 1,280 |
| Saved against control | — | 103 (7.45%) |
| Fused τ pairs | 0 | 59 |
| Cheap-Z fused pairs | 0 | 41 |
| Gauge table lookups | 0 | 59 |
| Target-specific prepared bytes | 1,104 | 1,104 |

The 103M saving uses the formula fixed in `PROTOCOL.md`; it counts only
the current startup evaluation formulas. It excludes recoding, gauge
lookups, batch normalization, inversion, and the rho walk. The generic
reference, control, and candidate also agree on 3,060 rho group
operations, 82 table entries, 8 table evaluations, 4 restarts, and all
12 ordered startup affine points. Their diagnostic point fingerprints
are `e756afd76dfe43bb` and `3d291bfcd25199eb` in both builds.
These 64-bit fingerprints aid trajectory checking; scalar replay is the
correctness certificate.

Local Release online medians from two observations per arm were
`0.3250 ms` for generic reference, `0.2665 ms` for the free-gauge
control, and `0.2750 ms` for the paired-τ candidate. The candidate was
slightly slower than its control in this exploratory panel despite its
lower formula count. UBSan medians were `2.6470`, `2.4600`, and
`2.4940 ms`, respectively. This host lacks a verified exclusive CPU
partition, NUMA policy, fixed frequency, IRQ control, and noise gates.
Both panels therefore record `cpu_speedup_claim: null` and
`isolation_receipt: null`; no controlled CPU speedup is claimed.

Release passed all 16 CTest tests. UBSan passed `curve` and `joint_tau`.
The isolated-manifest generator accepted this frozen fixture and
produced a one-case, 21-repetition dry-run manifest with 91 artifacts;
its placeholder cgroup is not an isolation receipt. A physical isolated
host run, broader curves, and an academic prior-art review remain
necessary. The mode stays opt-in.
