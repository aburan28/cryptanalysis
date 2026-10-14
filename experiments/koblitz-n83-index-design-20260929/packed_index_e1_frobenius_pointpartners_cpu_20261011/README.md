# E-1 Frobenius-shifted point partners for the N83 root index

The candidate removes 4,000,000 target-time basis conversions from the
batched point-partner implementation by storing each indexed root's lifted
`y` coordinate in polynomial form. For a query orientation with Frobenius
shift `s`, it evaluates the two partners of the unrotated root `R` against
`F^{-s}(Q)` and rotates each resulting root by `F^s` before canonical lookup.
Frobenius is a group automorphism on this Koblitz curve, so
`F^s(R +/- F^{-s}(Q)) = F^s(R) +/- Q`. The indexed root key, 16-byte record,
exact lookup, and first-inserted witness rule are unchanged.

The candidate and S3 reference use curve `EC1N83Ckb1h876c2921cb64`,
workload `981ac530e67e`, one frozen public target point, 2,000,000 sampled
pair states, 4,000,000 distinct root keys, and a 1,024 MiB RSS cap.
`Q2026101126` is the stage proposal ID; the complete IC candidate ID remains
null. Both arms end at `state_cap_no_relation`. The source SHA-256 is
`c9ead0921411e025e9651121e7e95e893224013598d8fa2fb6c434dd661ad1b7`.

| Exploratory local median | S3 reference | Frobenius point partners |
| --- | ---: | ---: |
| Target process CPU | 2.470 s | 2.150 s |
| Target query preparation wall | 2.332 s | 3.249 s |
| Target partner generation wall | 5.975 s | 4.349 s |
| Target partner check wall | 9.409 s | 9.355 s |
| Target stage wall | 17.678 s | 16.921 s |
| Target basis conversions | 12,000,000 | 12,000,000 |
| Target field multiplications | 43,998,533 | 19,998,533 |
| Target S3 calls | 4,000,000 | 0 |
| Index build process CPU | 1.021 s | 1.718 s |
| Nested index root-lift wall | — | 5.251 s |
| Additional indexed-root `y` storage | 0 | 64,000,000 bytes |
| Root-table allocation | 83,922,944 bytes | 83,922,944 bytes |

The candidate used fewer target process CPU seconds in all three adjacent
pairs. Six counterbalanced raw runs and exclusive target phase clocks are
retained in `run_*.json`, `run_*.record.json`, and `summary.json`.
`target_residual_ns` completes the phase sum to the charged target stage.
Root lifts and index construction are target independent and recorded
separately. This Mac host was contended; its wall times are exploratory.
The repository's physical-host isolation gate governs a controlled wall
comparison.

The full [N83 audit](audit_frobpointpartners.json) compared all 4,000,000
partner pairs after Frobenius rotation with the original S3 evaluator on
the original shifted roots. All 8,000,000 partner roots agreed, with
4,000,000 distinct indexed keys and peak RSS below the cap. Seven Rust tests
pass, including every curve-point pair over GF(32) and every shift in that
field. The wrapper replay independently checked each arm against frozen raw
output and produced the shared pair certificate
`01a3c02a7ca42fa75c6dfca9a0011ee2a83c66cca5487ff6a4446199223c0c16`.

`run.py` freezes the source/input hashes, workload, counterbalanced order,
limits, raw failures, stage costs, operation counts, and memory. The
`make_manifest.py` validator checks the full audit and replay certificate,
then constructs a six-repetition job for the isolated benchmark service.
The one-target IC/rho online comparison remains a separate full-pipeline
measurement.
