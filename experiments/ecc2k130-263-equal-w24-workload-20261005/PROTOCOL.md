# Frozen equal-size W24 four-policy workload

This protocol prepares exact, paired ECC2K-130 inputs for the still-open
four-policy point-decomposition comparison. It is a **base and workload
activation gate**, not a PDP run or an index-calculus candidate. The merged
W24 census supplies complete source and first degree-263 descendant mask
streams. The source has 8,393,232 signed subgroup classes; the descendant
has 8,386,414. Keep the first 8,386,414 source masks in ascending integer
order and all 8,386,414 descendant masks. Each selected geometry therefore
has exactly `B=16,772,828` distinct nonidentity subgroup-usable points
before sign folding. Record the selected source-prefix and native-stream
SHA-256 digests, boundary masks, actual `B`, and sign-only column count.
Do not assign an `IC1` candidate ID: the final point-set encoding, PDP,
relation matrix, target descent, and costs are not activated here.

The [configuration](CONFIG.json) pins the field modulus
`t^131+t^13+t^2+t+1`, the trace-zero `W24` basis, both complete archived
mask digests, curve IDs, and the verified oriented degree-263 route. Define
four policies using the same two geometries:

* `source`: the selected source `[4]`-projected W24 classes on the Koblitz
  curve;
* `transported`: their exact forward-isogeny images on the route's
  unnormalized descendant codomain;
* `descendant_native`: the selected native `[4]`-projected W24 classes on
  the normalized descendant, inverse-shifted onto the route's exact
  unnormalized codomain before they are stored or assigned a curve ID;
* `pullback`: the native classes returned to the source by the oriented
  dual and `263^(-1) mod r`.

The route's codomain model has `a4=A`; normalize it by `(x,y) -> (x,y+A)`
so `a4=0` and `b=a6+A^2`, exactly as in the W24 census. The inverse shift
is the same. The route's curve ID names the **unnormalized** model. Treat the
normalized model solely as an intermediate construction model and never
label its points with the route's curve ID. Check the forward kernel, dual
kernel, model coefficients,
generator transport, and both `263` composition identities before using
the maps. The transport is a group isomorphism on the prime-order subgroup,
so `source`/`transported` and `descendant_native`/`pullback` must later have
identical exact group-sum hit vectors on paired targets. This workload
only verifies those map and base-control identities; a practical implicit
PDP and its charged map costs remain open.

Freeze 64 control masks from each selected geometry. Use the policy strings
`source` and `descendant_native`; `transported` and `pullback` inherit the
corresponding selected indices. For a policy and counter starting at zero,
hash the UTF-8 string
`ecc2k130-equal-w24-control-v1:<policy>:<counter>` with SHA-256, reduce
the digest integer modulo 8,386,414 to select a zero-based position in its
ascending stream, and skip duplicates until 64 positions are retained.
Control indices are selected without examining point or solver outcomes.
For each selected mask, independently construct the curve point using the
frozen `w=u^2+u` and `[4]` rule, check subgroup order, forward/dual image,
normalization, and pullback identity. Preserve all selected indices, masks,
encoded points, outcomes, setup/evaluation time, and any failure. Timings
on this host are diagnostics only.

Freeze 512 previously unseen ordinary source targets. For counter starting
at zero, hash the UTF-8 domain
`ecc2k130-equal-w24-target-v1:` followed by the counter as eight
big-endian bytes; take the first 17 digest bytes, mask to 130 bits,
and reject zero, values at least the exact subgroup order, and duplicate
accepted scalars. The first 512 accepted values multiply the route's
source generator. This is fixture construction outside any future target
online interval. Store source public points and their forward images on the
route's exact unnormalized codomain in the workload; store the known fixture
scalars separately for independent replay, and do not pass them to a PDP
solver. Target zero is the sole primary one-target input. The other 511
public points are dormant reproducibility controls; do not run or report a
batch IC workload before the primary single-target study is complete.
Publish a separate `primary_workload.json` containing exactly target zero
and `target_count=1`. Hash its sorted-key compact UTF-8 record excluding
`workload_id` to form the primary 12-hex workload ID under `AGENTS.md`.
The 512-point control corpus has a separate identity and must never be used
as the one-target comparison ID. Freeze both sequences before measuring
any PDP.

An independent verifier must regenerate both mask-set digests directly
from the pinned gzip streams, reconstruct the maps from the saved kernel
polynomials, replay every target scalar against its source point and
forward image, check dual recovery and all 128 sampled base controls,
and reject any changed or missing field. Save the checked repository
`sage --runtime-info` receipt before each new Sage run. Keep the
source/input hashes, Sage runtime, raw successes and failures, setup cost,
transport evaluation cost, resource use, and verification certificate.
The corpus producer and verifier each have a one-worker 1,800-second wall
and 4-GiB RSS envelope; a timeout or OOM remains a result, not a pass.

This protocol does not choose a PDP solver or infer natural relation yield.
The follow-on protocol must freeze W24/m6 solver implementations, limits,
and ordinary-query prefix before consulting any target outcome. It must
retain every failed/timed-out attempt, useful rank, matrix and target costs,
and compare the four implementations at this equal actual `B`. Its paired
single-target IC-versus-rho claim still requires a complete verified DLP
and an isolated CPU receipt. Until then `candidate_id`, PDP yield, rank,
online/cold IC time, solved logarithm, and speedup remain `null`.
