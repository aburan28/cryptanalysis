# Low-degree horizontal search through depth five

The breadth-first search over horizontal isogenies of degrees 3, 5, 11, and 13
reached 168 unique curves through five hops. The shell sizes are 1, 6, 17, 32,
48, and 64 at depths zero through five. Every curve retains the complete path
from P-256, including kernel polynomials, rational maps, short-model
isomorphisms, and the transported generator. Every retained curve has the same
prime group order and geometric automorphism order two.

Deduplication against the prior 98-curve union left 112 previously unscreened
curves: 48 first reached at depth four and 64 first reached at depth five. The
combined explicit registry now contains P-256 plus 209 distinct neighbors.

## Matched native rho screen and holdout

All 112 new curves were screened with the same fixed-limb native Pollard-rho
backend used for P-256. Nineteen locally controlled blocks used 0.5-second
trials and one complete rotation through every timing position. All 776
candidate trials verified their scalar relation.

Six curves triggered the deliberately permissive, unadjusted screening rule.
The strongest screen estimate was 1.0880x with a paired 95% interval of
1.0297–1.1497x. A fresh holdout then measured P-256 and all six candidates for
30 two-second trials apiece, rotating their execution positions. None
reproduced. The strongest holdout estimate was 1.0153x with interval
0.9945–1.0366x; every interval included 1.0 and every relation verified.

Together with the earlier panels, all 209 explicitly retained non-root curves
now have matched native measurements and none has a reproducible iteration-rate
advantage.

## Cost and claim boundary

The Sage search recorded 48.89 seconds of reusable discovery time for the full
depth-five registry. The native screening block artifacts record 502.95 seconds
in aggregate, and the independent holdout recorded 431.48 seconds. These are
reported separately from per-key work. The formulas needed to map both ECDLP
points along every path are retained, but their evaluation was not timed for
these 112 additions, so no end-to-end amortized attack speedup is claimed.

This search is complete only for paths of at most five edges drawn from degrees
3, 5, 11, and 13. It neither enumerates the full P-256 isogeny class nor tests
larger path generators. The host CPU was not isolated, and the timings are
exploratory. A finite null screen cannot prove that no exceptional curve exists
elsewhere in the class.
