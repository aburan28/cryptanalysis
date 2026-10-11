# Resumed low-degree horizontal search through depth seven

The frozen depth-five frontier was resumed without recomputing or duplicating
its retained records. Horizontal isogenies of degrees 3, 5, 11, and 13 added 80
curves at depth six and 96 at depth seven. None overlapped the existing
210-curve union, so the combined explicit registry now contains P-256 plus 385
distinct neighbors.

All 176 additions retain their complete path from P-256, including kernel
polynomials, rational maps, short-model isomorphisms, and transported
generators. Every curve has the same prime group order and geometric
automorphism order two. The extension itself recorded 71.92 seconds of Sage
discovery time.

## CPU-separated native rho screen

The background class-group computation was pinned to CPU 4, while the native
screen and its child benchmark processes were pinned to CPU 0. The 176 new
curves were divided into 30 root-controlled blocks. Each block used 0.5-second
trials and one complete rotation through every timing position. All 1,224
candidate trials verified their scalar relation.

One depth-seven curve triggered the deliberately permissive unadjusted rule:
its path degrees were 11, 11, 11, 13, 13, 13, 13 and its screen estimate was
1.0714x with paired 95% interval 1.0052–1.1419x. A fresh 30-trial, two-second
holdout rejected it. The holdout estimate was 0.9886x with interval
0.9628–1.0151x, and every relation again verified.

Together with the earlier panels, all 385 explicitly retained non-root curves
now have matched native measurements and none has a reproducible iteration-rate
advantage.

## Cost and claim boundary

The native screening block artifacts record 795.89 seconds in aggregate, and
the independent holdout recorded 123.47 seconds. Discovery, screening, and
holdout costs are reported separately from per-key work. The formulas needed to
map both ECDLP points are retained, but their evaluation was not timed for these
176 additions, so no end-to-end amortized attack speedup is claimed.

This extension is complete only through depth seven for edge degrees 3, 5, 11,
and 13. It does not enumerate the full P-256 isogeny class, deeper paths, or
other degree generators. CPU affinity was separated, but frequency stability
was not independently verified. A finite null screen cannot prove that no
exceptional curve exists elsewhere in the class.
