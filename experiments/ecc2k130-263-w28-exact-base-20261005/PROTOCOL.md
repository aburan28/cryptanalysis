# Exact W28 base cardinality on the ECC2K-130 degree-263 route

This protocol precedes the exact W28 census. It extends the separately
published [W24 result](../ecc2k130-263-w24-exact-base-20261005/RESULT.md)
to the same paired source/first-descendant route and determines actual
usable base points and sign-folded columns for the competing W28/m5 policy.
There are no selected targets, planted decompositions, relation queries, or
timing-ratio claims. The exact field, route, curve IDs, normalized descendant
coefficient, mask order, resource limits, and decision thresholds are frozen
in [CONFIG.json](CONFIG.json).

Work in `GF(2^131)` with modulus `t^131+t^13+t^2+t+1`, and let
`W28=span(t^j+Tr(t^j), 1<=j<=28)`. Enumerate every nonzero 28-bit mask once,
in ascending integer order, and apply that same `w` to both curves. For a
normalized curve `y^2+xy=x^3+b`, put `alpha^4=b` and `w=u^2+u`.
The point with `x=alpha(1+1/u)` is rational exactly when
`Tr(alpha/w)=0`. The source has `alpha=1`; derive the descendant `alpha`
from the hash-pinned verified degree-263 route. Check `Tr(alpha)=1`, the
rational order-four point `(alpha,alpha^2)`, cofactor four, and the route's
prime subgroup order before accepting a count.

The [W24 proof](../ecc2k130-263-w24-exact-base-20261005/PROTOCOL.md)
shows that translation by the rational order-four point changes `w` to
`alpha/w`, and those two `w` values yield the same signed `[4]`-projected
subgroup point. Here `deg(w*w')<=56<130=deg(alpha)` for the descendant,
so two W28 values cannot be reciprocal partners. On the source, `w*w'=1`
would force both to be the constant 1, which is not trace-zero in this
odd-degree field. Consequently the predeclared collision count is zero:
if `R` nonzero masks pass the rationality predicate, there are exactly
`C=R` sign-folded columns and `B=2R` distinct nonidentity subgroup points.
The verifier must still check this class rule against full curve points;
any contradiction rejects the run.

The native producer will write one **two-bit membership code per mask**:
bit 0 is source rationality, bit 1 is descendant rationality. Pack four
ascending masks per byte, least-significant two-bit slot first. With
`2^28-1=268,435,455` masks, the raw stream is exactly 67,108,864 bytes;
the unused top two bits of the last byte must be zero. This is a lossless
encoding of both ordered canonical-mask lists: every set bit identifies its
mask, and the frozen field/half-trace/`[4]` rule reconstructs the signed
subgroup pair. The producer separately records source, descendant, and all
four paired rationality-cell counts; `C`, `B`, stream SHA-256, compiler,
backend, wall time, memory peak, source/input hashes, and failures.

Run the complete enumeration twice with inversion batch sizes 2,048 and
8,192. The two raw membership streams and all mathematical counts must
match byte for byte. The checked repository `sage` launcher must start each
new Sage job, and `./sage --runtime-info` must be saved before the measured
workload. Native census wall time and memory are diagnostic only on an
unisolated host. Each run's raw stream will be preserved in deterministic
gzip with a manifest binding compressed and decompressed hashes. Restoring
the archive into a fresh directory must reproduce its independent receipt.

The independent Sage verifier will re-count all four paired cells from the
complete bit stream without using the native summary, and it will check
4,096 distinct SHA-domain uniform masks by Sage field trace on **both**
curves. It will additionally select the first 32 masks in each of the four
rationality cells, plus 128 SHA-domain uniform full-width masks, and replay
rational cases through the curve law, the order-four translation, `[4]`
projection, subgroup order, and signed-point key. A separate d10 control
will exhaust all 1,023 nonzero masks and compare every projected signed
class to the prior W24 implementation; a portable C++ backend will match
the d10 stream. None of these controls substitutes sampled rationality for
the native exhaustive count.

The predeclared W28/m5 size gate is the [exact capacity result's](../ecc2k130-263-capacity-gate-20261004/RESULT.md)
minimum `B=60,591,280` for a 1% one-shot uniform-target **necessary**
multiset count. A passing `B` admits a held-out ordinary-query PDP/rank
panel; it does not establish a 1% hit rate. The descendant counts as a
material W28 geometry gain only if its exact rationality fraction exceeds
the source's by at least two percentage points, matching the earlier
sample-screen threshold. A smaller exact difference deprioritizes this
route as a density improvement, regardless of sign. The W28/m4 counting
bound will also be updated from actual `B`, but its maximum possible `B`
already misses the 1% size threshold.

The final report must preserve zero-yield or failed runs, exact paired
counts, both verified raw hashes, any censoring, and the distinction between
counting bounds and measured PDP coverage. No `IC1` candidate ID, natural
PDP rate, useful rank, matrix cost, target descent, logarithm, online IC
time, or rho speedup may be issued by this census. These fields remain
`null`; a formal `fb-archive` candidate record and equal-actual-`B`
four-policy PDP comparison remain follow-up work.
