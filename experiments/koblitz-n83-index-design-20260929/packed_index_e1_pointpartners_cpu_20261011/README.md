# E-1 batched point partners for the N83 root index

Precomputing one rational curve lift for each indexed S3 root lets the
one-target query generate its two partner x-coordinates by batched curve
addition. The frozen N83 query makes 4,000,000 partner requests. The new
path replaces those S3 calls with one batched inversion per query window,
then evaluates the x-coordinates of `R+Q` and `R-Q`. The packed root keys,
first-inserted witness selection, and exact-key lookup are unchanged.

For `R=(x,y)` and the public target `Q=(u,v)`, with `x != u`, put
`z=(x+u)^-1`, `lambda=(y+v)z`, and `delta=uz`. The two x-coordinates are
`lambda^2+lambda+x+u` and
`(lambda+delta)^2+(lambda+delta)+x+u`. Equal-x inputs use the original
S3 evaluator. A chosen sign of the precomputed lift only swaps these
two roots. Indexed roots are lifted before the target clock with batched
inversion; their chosen y-coordinates occupy 64,000,000 bytes. The
independent [full N83 audit](audit_pointpartners.json) compared all
4,000,000 partner pairs with the original S3 evaluator, preserving
8,000,000 target roots. Six Rust tests pass, including all curve-point
pairs over GF(32), varied inversion batch sizes, duplicate-key lookup,
and first-witness checks.

All panels use curve `EC1N83Ckb1h876c2921cb64`, workload
`981ac530e67e`, the same one public point, 2,000,000 indexed pair states,
4,000,000 exact root keys, and a 1,024 MiB RSS cap. Both arms finish at
`state_cap_no_relation`. Every panel summary has zero invariant mismatches.
The final audited-source panel recorded the following medians:

| Phase or resource | S3 reference | Batched point partners |
| --- | ---: | ---: |
| Target process CPU | 2.569 s | 2.336 s |
| Target query preparation wall | 3.303 s | 5.750 s |
| Target partner generation wall | 7.612 s | 2.863 s |
| Target partner check wall | 9.989 s | 7.608 s |
| Target stage wall | 21.505 s | 16.306 s |
| Index build process CPU | 0.986 s | 1.642 s |
| Nested root-lift preparation wall | — | 4.888 s |
| Additional root-y allocation | 0 | 64,000,000 bytes |
| Root-table allocation | 83,922,944 bytes | 83,922,944 bytes |
| Target field multiplications | 43,998,533 | 19,998,533 |
| Peak RSS median | 418,758,656 bytes | 506,134,528 bytes |

The target timer starts after root lifts, index construction, and the
lookup sample. Its three exclusive phases are query preparation, partner
generation, and partner check; `target_residual_ns` completes their sum
to the charged target stage. Root-lift preparation and its CPU and memory
costs are recorded separately under index construction. The two earlier
panels, retained in `exploratory_panel_1/` and
`pre_audit_source_panel_2/`, also had lower candidate target process CPU
in all six adjacent pairs. The final source had lower candidate CPU in
all three adjacent pairs. These are exploratory timings on a highly
contended Mac; the repository's physical-host isolation gate still governs
a controlled wall-time result.

`run.py` freezes the workload, source/input hashes, counterbalanced arm
order, limits, raw failures, phase clocks, operation counts, and memory.
`benchmark_stage.py` checks exact arm outputs and emits a shared pair
certificate; [replay_check.json](replay_check.json) records a successful
local wrapper replay. `make_manifest.py` validates all frozen inputs and
the full audit, then constructs the isolated-service job for a qualifying
physical host. The stage result is a bounded target-query comparison;
complete IC and paired rho online times remain unmeasured here.
