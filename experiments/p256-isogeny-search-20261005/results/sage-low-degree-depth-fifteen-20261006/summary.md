# Resumed low-degree horizontal search through depth fifteen

The degree-3/5/11/13 frontier added 208 curves at depth fourteen and 224 at
depth fifteen. None overlapped the existing 1,298-curve union, so the combined
explicit registry now contains P-256 plus 1,729 distinct neighbors.

All 432 additions retain complete ordered paths from P-256, including kernels,
rational maps, short-model isomorphisms, and transported generators. Every
curve has the same prime group order and geometric automorphism order two. Sage
discovery took 199.97 seconds.

## Native rho evidence

The additions were measured in 72 root-controlled blocks on CPU 0 while the
default exact class-group computation remained pinned to CPU 4. Every block
used 0.5-second trials and a complete timing-position rotation. All 3,024
candidate trials verified their scalar relation.

Seven curves triggered the permissive unadjusted screening rule, with point
estimates from 1.0412x through 1.0841x. A fresh holdout measured P-256 and all
seven for 30 two-second trials apiece. None reproduced. The largest holdout
estimate was 1.0151x with paired 95% interval 0.9878-1.0431x; every interval
included 1.0 and every relation verified.

Across all stages, all 1,729 retained non-root curves now have matched native
measurements and none has a reproducible iteration-rate advantage.

## Requirement-to-evidence status

| Requested component | Status | Evidence and boundary |
| --- | --- | --- |
| Frobenius discriminant / endomorphism orders | supported | The exact fundamental-discriminant certificate proves `Z[pi] = O_K`. |
| Explicit isogeny paths | supported within boundary | 432 new paths at depths 14-15; 1,730 total curves; degrees restricted to 3, 5, 11, and 13. |
| Exceptional automorphisms / low-norm endomorphism | refuted by exact structure | The CM field excludes exceptional `j`; the norm bound excludes a useful GLV-style endomorphism. |
| Non-generic ECDLP algorithm | not found within this family and boundary | This stage measures generic rho iteration cost only. |
| Unusually cheap operations | not found within this family and boundary | Seven screen positives all failed the fresh holdout. |
| Low-cost P-256 path | unknown for these additions | Explicit formulas exist, but both public-point evaluations were not timed. |
| Small-curve collision control | supported for the generic harness | The frozen toy run recovers its planted logarithm; no special structure was found to mirror. |
| Separate cost accounting | supported with open per-key item | Discovery, screen, holdout, and class-group work are reported separately. |

## Cost and claim boundary

| Phase | Measured cost | Scope |
| --- | ---: | --- |
| Depth-14/15 discovery | 199.9712 s | reusable path discovery |
| Native screening blocks | 1,961.0425 s | exploratory performance evidence |
| Fresh seven-candidate holdout | 493.3395 s | exploratory verification evidence |
| Per-key mapping of `P` and `Q` | unknown | not timed for these 432 paths |
| Default exact class-group computation | still running after 8 h 2 min | separate preprocessing; no result yet |

This is complete only through depth fifteen for degrees 3, 5, 11, and 13. It
does not enumerate the full finite class-group orbit, deeper paths, or other
generators. CPU affinity was separated, but host-wide isolation and frequency
stability were not independently verified. The bounded null result cannot
establish universal nonexistence of an implementation or algorithmic speedup.
