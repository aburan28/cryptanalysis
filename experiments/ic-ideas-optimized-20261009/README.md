# IC lead implementation and index-layout audit, 2026-10-09

The N53 three-summand target solver now has three lower-memory pair-index
implementations. The dense 32-bit-offset index preserved the exact
19,020,826-key geometry, triple witness, and recovered scalar
**6,141,872,670,687** while using 455.8 MB median peak RSS instead of
586.3 MB for the original hash map. Its target-dependent interval was
3.47 ms versus 3.11 ms in the paired local runs. The flat sorted index used
321.6 MB and 12.16 s median process CPU versus 14.50 s for the original,
but its random target lookup was slower. These CPU measurements are
exploratory: the host did not meet the repository's isolation gate.

An adaptive G1 F4 symbolic trace now completes every N31 cell completed by
fresh F4, with identical reduced bases and proof replay. It does more native
work overall, so fresh F4 remains the faster default. An exact G4
rationality-chain encoding completed all twelve paired N19 planted-target
cells through the installed Sage/Singular backend, using 16 variables and
18 equations versus 25 variables and 63 equations for the Boolean encoding.
The A2 N23 sparse family now has a 1 MiB exact membership bitset and support
map, checked against every field element and all Frobenius conjugates.
Checked Sage independently replayed all 17,296 encoded supports.

The previous suite's seven-lead validator still passes. This directory adds
implementations where the earlier result left a concrete path open, and
keeps the other leads at their measured or proved gates. All receipts have
`candidate_id: null`: these are component experiments, not a frozen complete
IC candidate with a paired isolated one-target rho comparison.

## Lead-by-lead result

| Lead | Implemented and checked | Current decision |
| --- | --- | --- |
| G1 | [`native_f4_adaptive.cpp`](native_f4_adaptive.cpp) reuses available symbolic multiples, then completes symbolic coverage on the new target. [`g1_adaptive.json`](g1_adaptive.json) records exact fresh basis, proof DAG replay, and exhaustive solution-set equality on 16/16 N31 m=2 and 15/15 completed m=3 cells. Both solvers hit the same cap on the remaining m=3 cell. | Adaptive work totals 285,600 versus 224,662 for m=2 and 1,025,969,247 versus 686,783,960 for the completed m=3 cells. Keep fresh F4 as default. |
| G2 | The preceding suite reconstructs degree-three binary Macaulay ranks from character blocks at N19 and N23 and records a 34.4 GB coefficient floor for one dense N131 nontrivial block. | A block-preserving F4 symbolic reduction and completed N19 baseline are still needed; the existing invariant N19 F4 run exhausted its 5-billion-work cap. Do not route solves through character blocks yet. |
| G3 | The preceding suite builds the complete N41 degree-four row stream and checks a sampled matrix-free transpose. It records 2,017,933 rows, 100,315,659 ambient columns, and 247,444,987 nonzeros. | Even full row rank leaves at least 98,297,726 ambient dimensions. A conventional 64-vector Wiedemann index stream was estimated at 124.8 TB. A higher-degree quotient and storage design are needed before a full sparse solve. |
| G4 | [`g4_exact_matched_panel.py`](g4_exact_matched_panel.py) uses the exact `z_i=z_0^(4^i), z_0=z_9^2` rationality chain. All 12 mixed and 12 Boolean N19 cells completed under a 45-second worker cap. Mixed Groebner times had median 1.60 s; Boolean times had median 4.70 s; mixed was lower on 8/12 paired cells. | These are local Sage/Singular `libsingular:std` stage diagnostics. The installed `msolve` backend rejects GF(2^19), so they are not a matched F4 result. The prior exhaustive rationality check removes eight false closure roots. |
| A1 | [`a1_n53_sorted_index`](a1_n53_sorted_index), [`a1_n53_bucket_index`](a1_n53_bucket_index), and [`a1_n53_offset_index`](a1_n53_offset_index) are full target solvers built from the same frozen base arithmetic. All twelve new paired target runs reproduce the original scalar; the same witness indices appear in every run. The previous suite solved the 60 seed logs from 111 verified ordinary relations in 128 queries. | The original hash map is the observed online-time default. Use the dense-offset index when the memory envelope is below the original ~586 MB peak. The sorted layout minimizes measured memory and index-build CPU but increases random target lookup time. The mixed hash-function candidate showed no CPU benefit and is retained only as a control. |
| A2 | [`a2_sparse_membership.py`](a2_sparse_membership.py) builds exact membership and support recovery for all 17,296 unique N23 weight-two/three sums of 47th-root powers. It checks all 2^23 field encodings and all 17,296 Frobenius support rotations. [`a2_sage_verify.json`](a2_sage_verify.json) independently replays every support in checked Sage. Compressed bitset and support map are 31,723 and 90,167 bytes. | The previous exhaustive audit proves degree-four Boolean equations leave 48 outside values, so this index is an exact lookup implementation rather than a degree-four F4 encoding. The F4/WDSat degree-five test remains open. The 17,296 x values are a representation family, not the count of subgroup-usable factor-base points. |
| N1 | The previous suite proves the augmentation condition for exact S3 lifts and tests 128 mixed sparse identities. Raw (2,3,3) sections lifted 0/128; repaired third leaves in 64/128 had minimum support 15–29. | The CRT lift is exact, but these sections do not yield the proposed sparse additive decomposition shortcut. |

## Matched A1 index controls

Each row is the median of two ABBA paired runs on the same frozen public
point and the same 60 verified seed logs. Process CPU includes base and
index construction, target work, and verification. Online time is measured
inside the solver after reusable setup. RSS is per-child maximum resident
memory. All timings are exploratory on this unisolated host.

| Layout | Process CPU, s | Peak RSS, MB | Index wall, s | Charged target online, ms |
| --- | ---: | ---: | ---: | ---: |
| Original hash map, sorted panel | 14.50 | 586.3 | 29.70 | 3.08 |
| Flat sorted records | 12.16 | 321.6 | 22.99 | 21.39 |
| Original hash map, bucket panel | 14.80 | 586.3 | 46.69 | 3.74 |
| Bucketed sorted records | 12.27 | 338.4 | 37.42 | 37.42 |
| Original hash map, offset panel | 14.61 | 586.3 | 46.90 | 3.11 |
| Dense records with 32-bit offsets | 14.93 | 455.8 | 49.30 | 3.47 |

The online sorted and bucket measurements show large scheduling variation;
their individual observations are in the JSON receipts. The offset values
were stable across the two runs: 3.478 and 3.464 ms. The hash-function-only
panel also preserved the witness, but process user CPU medians were 14.96 s
for the control and 15.00 s for the new mixer. That panel's macOS `time -l`
wrapper returned an error after each child because `kern.clockrate` was
unavailable; [`a1_hash_audit.json`](a1_hash_audit.json) verifies all four
completed child records and preserves the wrapper failures. The later panels
use `wait4` to record each child's CPU and RSS without that wrapper.

The receipts are [`a1_sorted_bench.json`](a1_sorted_bench.json),
[`a1_bucket_bench.json`](a1_bucket_bench.json), and
[`a1_offset_bench.json`](a1_offset_bench.json). They retain raw runs,
source and binary hashes, target and log input hashes, exact base hash,
phase timings, peak RSS, failures, and the independently checked witness.
The original public target and Sage scalar replay are in the
[`solver-gates`](../ic-ideas-solver-gates-20261008/README.md) suite.

## Reproducibility and limits

Run `python3 experiments/ic-ideas-optimized-20261009/validate_results.py`
and `python3 experiments/ic-ideas-solver-gates-20261008/validate_results.py`
from the repository root. The checked Sage runtime receipt is
[`sage_runtime_info.json`](sage_runtime_info.json). New local Sage jobs must
use `./sage -python`, including the G1 and G4 scripts. C++ control and
adaptive binaries used `c++ -O3 -std=c++20 -DNDEBUG`. The five Rust
packages share the workspace [`Cargo.lock`](Cargo.lock) and symlink to the
frozen arithmetic and build sources in the preceding suite. Build one
package at a time with `cargo build --release --locked -p <package>
--bin target_probe`; copy its executable before building another package
because each package's binary has the same name. The scripts preserve
existing outputs and should be rerun in a fresh copy.

The primary IC metric remains a verified one-target online comparison with
rho on that same point and an auditable host-isolation receipt. The results
here compare solver components and index layouts. The predecessor's N53
public-point recovery establishes correctness of the target path; a paired
isolated rho run is the next promotion step.
