# Independent Metal transform: retained results

Fresh validation completed on 2026-10-04 from committed source
`31d0038c88118dbbd8ae1f0f94a50f35c1771c41` on a physical Apple M4 Pro
(14 physical/logical CPU cores, 48 GiB, ARM64, macOS 26.6, Python 3.13.1).
The source receipt binds 306 files; all match their committed Git blobs.
The complete-query report binds 557 source, generated and native artifacts.

| Correctness check | Result |
| --- | --- |
| Optimized native transforms | 168 controls, each checked twice; pass |
| UBSan native transforms | Same 168 controls, each checked twice; pass |
| Explicit unavailable backend | Pass |
| Certificate API test groups | 7 pass |
| Fresh complete queries across 18 frozen inputs | 324 pass |
| Original-ANF independent audit | All 324 records; 35 distinct proofs pass |
| Balanced complete-query diagnostic | 162 successful fresh queries |
| Retained-artifact source/binary audit | Pass; archived binaries never loaded |

The full panel covers 6–27 Boolean variables, six producer/checker/build modes,
and serial, prepared and overlapping preparation. It retains exact proof/basis
identities, original-equation checks, full-point curve replay, fresh inputs,
budget behavior and prepared-generation ownership. Native controls include
32/64-bit coefficients and the actual 48,234,496-byte large table. This is a
projection/evaluation certificate checker, not a general GPU F4/F5 solver.

## Exploratory timing only

The producer is Metal in every diagnostic arm. The checker arm changes between
CPU, stagewise Metal and SIMD-fused Metal. Each row has 18 fresh complete-query
observations; all six arm orders appear three times. Reusable context/shader
setup is separately recorded. The charged interval includes fresh coefficient
copies, dispatch, synchronization, solving, independent certificate checking,
original equations and public-point replay. The transform column is nested in
the complete-query interval and must not be added to it.

| Frozen fixture | Checker arm | Median complete query (ms) | Complete-query IQR (ms) | Median transform (ms) |
| --- | --- | ---: | ---: | ---: |
| n31-m3-ell6-seed101 | cpu | 1.023 | 0.979–1.043 | 0.080 |
| n31-m3-ell6-seed101 | metal | 1.161 | 1.124–1.233 | 0.199 |
| n31-m3-ell6-seed101 | metal_simd | 1.139 | 1.122–1.162 | 0.167 |
| n31-m3-ell8-seed201 | cpu | 14.931 | 14.768–15.137 | 2.817 |
| n31-m3-ell8-seed201 | metal | 14.622 | 14.443–14.756 | 2.438 |
| n31-m3-ell8-seed201 | metal_simd | 13.558 | 13.446–13.715 | 1.404 |
| n31-m3-ell9-seed201 | cpu | 120.481 | 119.102–122.128 | 14.946 |
| n31-m3-ell9-seed201 | metal | 119.465 | 118.397–120.478 | 13.880 |
| n31-m3-ell9-seed201 | metal_simd | 112.584 | 111.516–113.288 | 7.751 |

IQR is descriptive sample spread, not a confidence interval or a familywise
claim. The one-minute host load ranged from 9.838 to 10.085. There is no
host-level isolation receipt. `timing_eligible` is false; controlled CPU/GPU
crossover, aggregate speedup and one-target IC/rho speedup remain unknown.
CPU stays the default; Metal remains explicit and capability checked.
The small fixture still favors CPU; larger fixtures motivate removing checker
copy costs and profiling the remaining identity/certificate work. These data
do not establish an asymptotic improvement or an F6 algorithm.

## Evidence and reproduction

`results/` retains every diagnostic query, frozen order, setup costs, source and
binary receipt, original-ANF audit, per-query correctness metadata, proof
hashes, test logs and a SHA-256/size index of the complete local artifact tree.
The approximately 35 MiB raw proof bundle is retained outside Git at the path
in `retained-artifacts.json.gz`; the compact metadata file omits only proof
payloads and cannot independently replay them. Run the commands in `README.md`
to regenerate the full bundle and original-ANF audit. The CI workflow rebuilds
native code separately on Linux and macOS and uploads the complete evidence,
including proofs, for 14 days. It records an unavailable GPU explicitly.

All rows are synthetic algebra/PDP controls. They do not measure natural
relation yield, recovered discrete logarithms, or IC speedup against rho.
