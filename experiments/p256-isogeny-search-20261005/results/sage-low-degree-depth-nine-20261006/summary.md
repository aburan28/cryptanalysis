# Resumed low-degree horizontal search through depth nine

The depth-seven frontier was resumed using horizontal isogenies of degrees 3,
5, 11, and 13. It added 112 curves at depth eight and 128 at depth nine. None
overlapped the existing 386-curve union, so the combined explicit registry now
contains P-256 plus 625 distinct neighbors.

All 240 additions retain their complete path from P-256, including kernel
polynomials, rational maps, short-model isomorphisms, and transported
generators. Every curve has the same prime group order and geometric
automorphism order two. The extension itself recorded 102.33 seconds of Sage
discovery time.

## CPU-separated native rho screen

The background class-group computation remained pinned to CPU 4, while the
native screen and holdout were pinned to CPU 0. The 240 new curves were divided
into 40 root-controlled blocks. Each block used 0.5-second trials and one
complete rotation through every timing position. All 1,680 candidate trials
verified their scalar relation.

Six curves triggered the permissive, unadjusted screening rule, with point
estimates from 1.0448x through 1.0751x. A fresh holdout measured P-256 and all
six candidates for 30 two-second trials apiece. None reproduced. The strongest
holdout estimate was 1.0312x with paired 95% interval 0.9975–1.0660x; every
interval included 1.0 and every relation verified.

Together with the earlier panels, all 625 explicitly retained non-root curves
now have matched native measurements and none has a reproducible iteration-rate
advantage.

## Cost and claim boundary

The native screening block artifacts record 1,091.41 seconds in aggregate, and
the independent holdout recorded 432.08 seconds. Discovery, screening, and
holdout costs are reported separately from per-key work. The formulas needed to
map both ECDLP points are retained, but their evaluation was not timed for these
240 additions, so no end-to-end amortized attack speedup is claimed.

This extension is complete only through depth nine for edge degrees 3, 5, 11,
and 13. It does not enumerate the full P-256 isogeny class, deeper paths, or
other degree generators. CPU affinity was separated, but frequency stability
was not independently verified. A finite null screen cannot prove that no
exceptional curve exists elsewhere in the class.
