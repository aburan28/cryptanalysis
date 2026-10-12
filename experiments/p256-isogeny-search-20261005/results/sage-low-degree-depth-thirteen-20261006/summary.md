# Resumed low-degree horizontal search through depth thirteen

The depth-eleven frontier was resumed using horizontal isogenies of degrees 3,
5, 11, and 13. It added 176 curves at depth twelve and 192 at depth thirteen.
None overlapped the existing 930-curve union, so the combined explicit registry
now contains P-256 plus 1,297 distinct neighbors.

All 368 additions retain their complete ordered path from P-256, including
kernel polynomials, rational maps, short-model isomorphisms, and transported
generators. Every curve has the same prime group order and geometric
automorphism order two. The extension recorded 170.11 seconds of Sage
discovery time.

## Transfer and native controls

Every retained path is a composition of explicit F_p-rational separable
isogenies. Each edge degree differs from the prime subgroup order, so the
kernel intersects the ECDLP subgroup trivially and the induced group map
preserves the discrete logarithm. This is checked structurally through path
continuity, mapped generators, and degree products, and empirically through the
tracked scalar relation after every timed native trial.

The 368 new curves were divided into 62 root-controlled blocks on CPU 0 while
the default exact class-group computation remained pinned to CPU 4. Blocks
used 0.5-second trials and complete timing-position rotations. All 2,568
candidate trials verified their scalar relation.

Sixteen curves triggered the permissive, unadjusted screening rule, with point
estimates from 1.0454x through 1.1146x. A fresh holdout measured P-256 and all
sixteen candidates for 30 two-second trials apiece. None reproduced. The
largest holdout estimate was 1.0179x with paired 95% interval
0.9920-1.0445x; every interval included 1.0 and every relation verified.

Together with the earlier panels, all 1,297 explicitly retained non-root
curves now have matched native measurements and none has a reproducible
iteration-rate advantage.

## Requirement-to-evidence status

| Requested component | Status | Evidence and boundary |
| --- | --- | --- |
| Frobenius discriminant and endomorphism orders | supported | The exact fundamental-discriminant certificate still proves `Z[pi] = O_K`. |
| Explicit isogeny paths | supported within boundary | 368 new paths at depths 12-13; 1,298 total curves; edges restricted to 3, 5, 11, and 13. |
| Exceptional automorphisms / `j` | refuted for the class by exact structure | The CM field excludes `j = 0, 1728`; all new curves also report geometric automorphism order two. |
| Efficient low-norm endomorphism | refuted by exact structure | The 256-bit lower norm bound excludes a useful GLV-style endomorphism. |
| Non-generic ECDLP algorithm | not found within this family and boundary | This stage tests generic rho iteration cost, not universal algorithmic nonexistence. |
| Unusually cheap group operations | not found within this family and boundary | All 16 screen positives failed the fresh holdout; host isolation remains unverified. |
| Low-cost P-256 path | unknown for these additions | Explicit formulas exist, but evaluating both public points was not timed. |
| Small-curve collision control | supported for the generic harness | The initial frozen toy run recovers its planted logarithm; no special structure was found to mirror. |
| Discovery versus per-key accounting | supported with an open per-key item | Discovery, screen, holdout, and exact-class-group work remain separate. |

## Cost and claim boundary

| Phase | Measured cost | Scope |
| --- | ---: | --- |
| Depth-12/13 discovery | 170.1121 s | reusable path discovery |
| Native screening blocks | 1,669.1968 s | exploratory performance evidence |
| Fresh sixteen-candidate holdout | 1,048.7284 s | exploratory verification evidence |
| Per-key mapping of `P` and `Q` | unknown | not timed for these 368 paths |
| Default exact class-group computation | still running after 7 h 8 min | separate reusable preprocessing; no result yet |

This extension is complete only through depth thirteen for edge degrees 3, 5,
11, and 13. It does not enumerate the full P-256 isogeny class, deeper paths,
or other degree generators. CPU affinity was separated, but host-wide
isolation and frequency stability were not independently verified. A bounded
null screen cannot prove that no exceptional implementation or non-generic
algorithm exists elsewhere in the finite class-group orbit.
