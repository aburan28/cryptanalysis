# Frozen degree-263 polynomial-W factor-base screen

This is a bounded **stage** comparison on the exact ECC2K-130 degree-263
route `IW1E263d1hadee4e69fa3d`. The hypothesis is that the first descending
codomain might admit materially more rational polynomial-W base parameters
than the Koblitz source at the same nominal dimension. The reference is the
source on the **same masks**, not a separately sampled base. The exact route
manifest is `experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json`,
SHA-256 `4b8ce3b607f9fd34c64a157cc904a00b8350e48570d1eaac7b4ca0646f296075`.
This protocol and [CONFIG.json](CONFIG.json) are committed before any new
mask or outcome is generated. The original pin to an older local copy failed
at the first hash assertion, before any mask generation; the preflight and
correction are retained in [PRECHECK.md](PRECHECK.md). Prior untracked exploratory screens suggested
roughly one-half rationality; they are not accepted input data for this run.

For each `d` in 24, 28 and 35, let
`W_d = span_F2(t^j + Tr(t^j) : 1 <= j <= d)` in the route's exact
`F_2[t]/(t^131+t^13+t^2+t+1)` representation. Assert the listed basis has
binary rank `d`. Draw 16,384 distinct, nonzero `d`-bit masks by SHA-256
rejection sampling with the domain string, `d` and a monotone counter. Reuse
each mask on both curves. On normalized `y²+xy=x³+b`, set `alpha^4=b` and
`w=u²+u`. A nonzero `w` yields rational lifts exactly when
`Tr(alpha/w)=0`. Reconstruct the first codomain's normalized `b` from the
route manifest's `a4,a6` as `b=a6+a4²`; derive `alpha` as the unique fourth
root. The source has `b=alpha=1`.

Archive every mask and both predicate outcomes. Independently recompute
all masks, predicates, counts, paired discordances and capacity bounds in a
separate verifier. For the first 32 rational masks on each curve/dimension,
construct both `u` roots and rational signs, check curve membership,
translation by the rational order-two point, identical `[4]` projection,
nonidentity subgroup membership, and sign covariance. This is a sampled
group-law control; the trace predicate is applied to every sampled mask.
Tie the normalized codomain to the exact manifest curve and generator, but
do not infer a new isogeny route or a conductor from this screen.

The primary statistic is the paired descendant-minus-source rationality
fraction `(descendant_only-source_only)/16384`. Report its approximate
two-sided 95% paired interval using the variance of values in `{-1,0,1}`;
retain both discordant counts. A **material gain** requires the interval's
lower endpoint to exceed `0.02`. If its upper endpoint is below `0.02`,
report that this frozen screen did not support a two-point material gain.
Otherwise report inconclusive. No seed, dimension, sample, or threshold may
be selected after reading outcomes. Timings on this host are exploratory.

For each `d`, prove the unconditional maximum projected nonidentity base
size `B_max=2(2^d-1)`: each nonzero `w` has two `u` roots related by rational
2-torsion translation, so their `[4]` images coincide up to sign. For each
listed smaller arity `m=(5,4,3)` at `d=(24,28,35)`, compute the exact
uniform-nonidentity support upper bound
`min(1, binomial(B_max+m-1,m)/(r-1))`. This is a counting bound, not an
estimate of actual natural relation yield or proof of fixed-target support.

Use the repository's checked `/Volumes/SSD990/cryptanalysis/sage` launcher
for every Sage command. Save its `--runtime-info` output before the measured
job. Preserve the first execution and any failures, source/config/route
hashes, wall/RSS, and the independently generated verification receipt.
The producer cap is 600 seconds and 1 GiB; a cap breach is censored, and a
group-law or verifier mismatch fails the screen. Do not retry with new masks.
No candidate ID, completed base, implicit PDP cost, relation rank, matrix,
target logarithm, or rho speedup is claimed; those fields remain null. A
material rationality result would justify an equal-actual-B four-policy
natural-target PDP experiment. Without one, this particular W family is
deprioritized while other codomain base constructions remain open.
