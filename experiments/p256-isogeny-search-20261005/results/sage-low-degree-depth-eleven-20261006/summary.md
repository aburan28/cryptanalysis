# Resumed low-degree horizontal search through depth eleven

The depth-nine frontier was resumed using horizontal isogenies of degrees 3,
5, 11, and 13. It added 144 curves at depth ten and 160 at depth eleven. None
overlapped the existing 626-curve union, so the combined explicit registry now
contains P-256 plus 929 distinct neighbors.

All 304 additions retain their complete ordered path from P-256, including
kernel polynomials, rational maps, short-model isomorphisms, and transported
generators. Every curve has the same prime group order and geometric
automorphism order two. The extension itself recorded 125.93 seconds of Sage
discovery time.

## Typed correspondence and controls

Each retained path has the form

```text
E_0(F_p)[n] --phi_1--> E_1(F_p)[n] --...--> E_d(F_p)[n],  d in {10, 11}
```

where each `phi_i` is an explicit F_p-rational separable isogeny of degree 3,
5, 11, or 13. Because the subgroup order `n` is prime and differs from every
edge degree, the kernel intersects the ECDLP subgroup trivially. The stored
maps transport the P-256 generator, while every timed native trial independently
checks the tracked scalar relation. This establishes log preservation for the
retained paths; it does not measure their per-key evaluation cost.

## CPU-separated native rho screen

The background default class-group computation remained pinned to CPU 4, while
the native screen and holdout were pinned to CPU 0. The 304 new curves were
divided into 51 root-controlled blocks. Each block used 0.5-second trials and
one complete rotation through every timing position. All 2,120 candidate
trials verified their scalar relation.

Eight curves triggered the permissive, unadjusted screening rule, with point
estimates from 1.0260x through 1.1525x. A fresh holdout measured P-256 and all
eight candidates for 30 two-second trials apiece. None reproduced. The largest
holdout estimate was 1.0220x with paired 95% interval 0.9918-1.0531x; every
interval included 1.0 and every relation verified.

Together with the earlier panels, all 929 explicitly retained non-root curves
now have matched native measurements and none has a reproducible iteration-rate
advantage.

## Requirement-to-evidence status

| Requested component | Status | Evidence and boundary |
| --- | --- | --- |
| Frobenius discriminant and endomorphism orders | supported | `D_pi` is exactly certified fundamental, so `Z[pi] = O_K`; the structural report remains the controlling evidence. |
| Isogeny exploration with explicit P-256 paths | supported within boundary | 304 new paths at depths 10-11; 930 total unique curves; edge degrees restricted to 3, 5, 11, and 13. |
| Extra automorphisms / exceptional `j` | refuted for the class by exact structure | The CM field excludes `j = 0, 1728`; every newly reached curve also reports geometric automorphism order two. |
| Efficient low-norm endomorphism | refuted by exact structure | The fundamental discriminant gives a 256-bit lower bound for a non-scalar norm; no GLV-style low-degree endomorphism exists. |
| Non-generic ECDLP algorithm | not found within this family and boundary | This stage tests generic rho iteration cost only; it does not prove universal nonexistence. |
| Unusually cheap group operations | not found within this family and boundary | Eight short-screen positives all failed the fresh holdout. Host isolation remains unverified, so timing is exploratory. |
| Low-cost P-256 path | unknown for the additions | Explicit formulas are retained, but path evaluation on both public points was not timed at depths 10-11. |
| Small-curve collision control | supported for the generic harness | The frozen initial toy control recovers its planted logarithm. No new exceptional structure was found to instantiate in an analogous toy family. |
| Discovery versus per-key accounting | supported with an open per-key item | Discovery, native screen, holdout, failed exact-class-group attempts, and the still-running exact computation are separated; new path-evaluation cost remains unknown. |

## Cost and claim boundary

| Phase | Measured cost | Reuse / scope |
| --- | ---: | --- |
| Depth-10/11 discovery | 125.9279 s | reusable path discovery |
| Native screening blocks | 1,376.8950 s | exploratory performance evidence |
| Fresh eight-candidate holdout | 555.2603 s | exploratory verification evidence |
| Per-key mapping of `P` and `Q` | unknown | not timed for these 304 paths |
| Default exact class-group computation | still running | separate reusable preprocessing |
| Independent `tech=[6,6]` class-group attempt | 15,918 s, preempted | no mathematical result; preserved failure cost |

This extension is complete only through depth eleven for edge degrees 3, 5,
11, and 13. It does not enumerate the full P-256 isogeny class, deeper paths,
or other degree generators. There are infinitely many composed isogeny maps,
even though the F_p-isomorphism classes in the ordinary isogeny class form a
finite class-group orbit. CPU affinity was separated, but host-wide isolation
and frequency stability were not independently verified. A finite null screen
cannot prove that no exceptional implementation or non-generic algorithm exists
elsewhere in the class.
