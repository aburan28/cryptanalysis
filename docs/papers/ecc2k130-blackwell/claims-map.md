# Claim-to-evidence map

All implementation paths below are relative to `ecc2k130/research/candidates/goal22/`. The paper is tied to that archive, not to a changing production profile.

| Manuscript claim | Primary evidence | Scope |
| --- | --- | --- |
| 22.100934 B/s and 11.3243% improvement | `measurement.json`, `samples`, `summary`; independently recomputed in `evidence/analysis.json` | Five confirmation runs per configuration on one GPU |
| 21.548499 B/s collection | `variants.warps4_poly_compact640.collection` | One sample; no repeated collection confidence interval |
| Exact completed counts | Sample geometry and full final output; `src/main.cu` | Scheduled scalar slots; includes arithmetic after a trail is marked dead until reseed |
| Collection timing includes report processing | `src/main.cu` timer and final synchronization | Startup and final file close excluded; no cloud/database throughput claim |
| Frozen source identity | Original `source-manifest.json`; all 119 files rehashed | Source integrity, not a new GPU run |
| Table-walk selector and cycle rule | `include/tablewalk.h`, `include/packedtablewalk.cuh`, `include/ref.h` | Point-plus-history transition; no random-map proof |
| Raw-selector equivariance | Explicit equations derived from those files | Nonexceptional selector domain; history issue separate |
| Five-word field and native products | `include/packed131.h` | Actual selected multiplier, not all experimental branches |
| Multiplication count 5 + 5/(BW) | Weighted prefixes in `include/packedkernels.cuh`; `include/collective_inverse.cuh` | Ordinary nonzero-denominator affine domain; excludes linear maps, synchronization, memory |
| Exact compressed square map | `research/gen_square_reduce.py`, `include/square_reduce.h` | All 131 basis inputs establish the linear identity; additional finite cases support implementation |
| Irreducible internal degree-131 modulus | New independent local polynomial checks in `analyze_evidence.py` | Exact field-polynomial check, not a cryptanalytic experiment |
| 94 registers and zero local bytes | Every candidate sample's raw runtime output | Runtime-reported resource attributes for the measured configuration |
| Compact flags use bytes | `include/compact_metadata.cuh` and final probe output | Earlier bit-packed experimental variants are not the accepted configuration |
| Independent GPU probes | `measurement.json`, `probes`, `probe`, `zip_collective_probes` | Recorded functional coverage; no sanitizer pass |
| 300 replays and full corpus equality | `variants.*.replay`, `reports_ok`, `corpus` | Full persisted multiset compared across builds; only 300 reports independently rewalked |
| Checkpoint continuation | Candidate `resume_checks` | Two directions at matching batch/population |
| Higher screens excluded | Research notebook and final confirmation receipt | No substitution of warmup or screening rates for final median |
| Exception limitation | `include/ref.h`, `TableWalk::step`; raw GPU affine formulas | Baseline agreement does not prove complete group law |
| Global state-of-the-art status | No exhaustive comparable evidence supplied | Paper does not assert a fastest-solver record |

Literature was checked against the primary ECC2K-130 papers, original collision-search and arithmetic literature, publisher records, and NVIDIA's PTX ISA documentation on September 21, 2026. The raw throughput figures are local measured evidence, not values inferred from older memory notes.
