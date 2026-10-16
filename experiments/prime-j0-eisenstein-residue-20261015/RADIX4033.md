# Norm-4033 Eisenstein radix for scalar-local multiplication

The scalar-local path can use `π = 64+ω = 65−τ`, whose hexagonal norm is **4033**. Its Horner action is six doublings, one order-three x rotation, and one projective addition. The [hash-guarded overlay](native_sparse_radix4033_overlay.py) also changes the nearest-digit selector, exact quotient matrix, and step count from 20 to 22. The quotient is cyclic with `τ ≡ 65 (mod 4033)`; primality of the norm is not required for the recorded division and replay. The [Lean module](Radix4033.lean) checks the norm, adjugate identities, exact quotient under the selector congruence, and rotation identity. Its [fresh pinned receipt](radix4033-lean-check.json) records five axiom audits. A full proof that the executed selector always meets the congruence and terminal bound remains open; the native full-fixture replay below tests those conditions on the frozen workload.

## Paired Tier 1 measurements

The committed [one-scalar](tier1-radix4033-1-cpu40-manifest.json) and [128-point](tier1-radix4033-128-cpu40-manifest.json) plans compare norm 4033 with the norm-7009 rotated path on identical inputs, CPU 40, and 16 alternating repeats with adjacent A/A controls. Their [rules](tier1-radix4033-1-cpu40-rules.json) and [rules](tier1-radix4033-128-cpu40-rules.json) freeze the `[0.90,1.11]` noise gate and paired interval criterion. The Rust interval includes recoding, graph digit synthesis, and Horner evaluation; process launch, fixture loading, and external replay are outside it.

| Workload | Norm-7009 mean | Norm-4033 mean | Qualified paired reference/candidate median | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| One scalar | 0.542 ms | 0.471 ms | 1.140× | [1.130, 1.144] |
| 128 points | 39.500 ms | 38.959 ms | 1.017× | [1.010, 1.019] |

The [independent auditor](analyze_tier1_radix4033.py) checked source and binary hashes, every command/stdout/stderr and pair record, independent scalar replay of measured points, stable artifacts, and all A/A controls. Each panel completed **96 valid arms and 48 valid pairs**. The [one-scalar launch](tier1-radix4033-1-cpu40-launch.json), [audit](tier1-radix4033-1-cpu40-audit.json), and [raw archive](radix4033-1-raw.tar.gz) identify job `5198a67ca1fb418884feeb1585ad7d67`; the [128-point launch](tier1-radix4033-128-cpu40-launch.json), [audit](tier1-radix4033-128-cpu40-audit.json), and [raw archive](radix4033-128-raw.tar.gz) identify job `8fd7116208d94dee871413c6e33b4859`. The [native provenance](radix4033-native-provenance.tar.gz) carries both exact source trees, binaries, overlays, fixture, and build output. The initial [128-point correctness pilot](tier1-radix4033-128-pilot-cpu40-launch.json) and [raw record](radix4033-128-pilot-raw.tar.gz) are retained separately.

## Full-fixture replay

The separately [frozen manifest](tier1-radix4033-full-replay-cpu40-manifest.json) and [rules](tier1-radix4033-full-replay-cpu40-rules.json) sent two identical candidate arms through the serial queue. Job `1d3cf18c0fc94bf3b4c9646d783156f2` verified all **12,288** frozen outputs in each arm with stable artifacts. The [auditor](analyze_tier1_radix4033_full_replay.py), [launch](tier1-radix4033-full-replay-cpu40-launch.json), [audit](tier1-radix4033-full-replay-cpu40-audit.json), and [raw archive](radix4033-full-replay-raw.tar.gz) preserve the exact run. The two intervals were **3.652 s** and **3.670 s**. This A/A correctness run has a null speedup field.

The one-scalar gain is measured on the recorded Tier 1 cloud instance. Replication on another allocation and a complete selector/terminal proof are the next gates for a broader algorithmic claim.
