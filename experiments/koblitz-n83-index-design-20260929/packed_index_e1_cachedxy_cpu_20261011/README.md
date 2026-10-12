# E-1 cached polynomial root coordinates for the N83 index

The candidate retains each indexed S3 root's polynomial x coordinate when
precomputing its lifted y coordinate. The target query reads both values
from the index and evaluates batched point partners against the inverse
Frobenius conjugate of the public point. Rotating each partner back before
canonical lookup preserves the exact root key and first-inserted witness.
This removes 4,000,000 target-time basis conversions from the prior
Frobenius point-partner implementation. The root index remains a sparse
24-bit bitmap-rank directory with 16-byte exact-key records.

Both arms use curve `EC1N83Ckb1h876c2921cb64`, workload `981ac530e67e`,
one frozen public target, 2,000,000 sampled pair states, 4,000,000
indexed root keys, and a 1,024 MiB RSS cap. `Q2026101127` is the stage
proposal ID; the complete IC candidate ID remains null. Both arms record
`state_cap_no_relation`. The native source SHA-256 is
`33a3c06141c82142efd11fe9f82540761bc361985383cb49c5eb03d28055824a`.

| Exploratory local median | S3 reference | Cached x/y point partners |
| --- | ---: | ---: |
| Target process CPU | 2.247 s | 1.671 s |
| Target query preparation wall | 0.530 s | 0.215 s |
| Target partner generation wall | 1.077 s | 0.621 s |
| Target partner check wall | 1.135 s | 1.253 s |
| Target stage wall | 2.745 s | 2.055 s |
| Target basis conversions | 12,000,000 | 8,000,000 |
| Target field multiplications | 43,998,533 | 19,998,533 |
| Target S3 calls | 4,000,000 | 0 |
| Index build process CPU | 0.933 s | 1.482 s |
| Nested index root-lift wall | — | 0.760 s |
| Indexed-root x/y allocation | 0 | 128,000,000 bytes |
| Root-table allocation | 83,922,944 bytes | 83,922,944 bytes |
| Peak RSS | 576,536,576 bytes | 614,858,752 bytes |

The candidate used fewer target process CPU seconds in all three adjacent
pairs. Six counterbalanced raw runs, including their failures and exact
exclusive target phases, are retained in `run_*.json`, `run_*.record.json`,
and `summary.json`. `target_residual_ns` completes each phase sum to the
charged target stage. The x/y cache, index build, and root lifts are
precomputed before the one-target clock and recorded separately. The local
wall times are exploratory because this host lacks an isolation receipt.

The full [N83 audit](audit_cachedxy.json) compared all 4,000,000 partner
pairs after Frobenius rotation with the original S3 evaluator on the
original shifted roots. All 8,000,000 partner roots agreed; all 4,000,000
indexed keys and the first-witness lookup sample were preserved. The audit
peak RSS was 617,644,032 bytes. Seven Rust tests pass, including every
curve-point pair over GF(32) and every Frobenius shift in that field. Both
wrapper replays independently checked their frozen raw outputs and shared
pair certificate
`01a3c02a7ca42fa75c6dfca9a0011ee2a83c66cca5487ff6a4446199223c0c16`.

`run.py` freezes source/input hashes, the workload, counterbalanced order,
limits, raw failures, stage costs, operation counts, and memory.
`make_manifest.py` validates the full audit and replay certificate and
constructs a six-repetition job for the isolated benchmark service. The
physical-host replay determines a controlled wall-time comparison; full
one-target IC/rho accounting is a subsequent pipeline measurement.
