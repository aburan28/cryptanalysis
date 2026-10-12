# Verified equal-B public inputs for six ECC2K-130 base policies

The six frozen policies now have the same **11,743,888 actual subgroup-usable
factor-base points** and a common stream of **65,536 ordinary public query
pairs** on the source curve and its verified degree-263 descendant. The full
ordered public-point stream has paired SHA-256
`0ceb47f484ab065f34d9d9c5af24b0ff189db15b8d6378d51d1018378a32bd25`.
A separate checked-Sage implementation reconstructed every query point by a
different fixed-base addition schedule and matched that digest, the first
16/256 prefix digests, and 80 direct scalar/isogeny samples. The
[R1 manifest](runs/R1/manifest.json) binds all source, input, runtime, and
result files by SHA-256.

## Exact inputs and geometry

The field is `GF(2^131)` in polynomial basis modulo
`t^131+t^13+t^2+t+1`. The source is
`EC1N131Ckb1h136f03e58c98`; the exact unnormalized descendant is
`EC1N131Cbinh833014327b07`, connected by verified route
`IW1E263d1hadee4e69fa3d`. The prime subgroup has order
`680564733841876926932320129493409985129`. The one-target public-point
workload remains `eee7f6ee5f6b`; its source and descendant points were
replayed from the fixture scalar and checked through the forward and dual
maps. The ordinary queries are target-independent preparation inputs.

| Base policy input | Exact usable points `B` | Signed classes `C` | Frozen identity |
| --- | ---: | ---: | --- |
| Source W24 prefix | 11,743,888 | 5,871,944 | selected raw mask SHA-256 `63be4963f28ecabbf93e72b063e7264fa2e3f24a8534fc9d1c38fd22705f7d79` |
| Descendant-native W24 prefix | 11,743,888 | 5,871,944 | selected raw mask SHA-256 `5aa0b2c3f85e0babdec4f772bb0f8f0285725d92d7217bbaa1f9429f9647d790` |
| Source normal-weight-four | 11,743,888 | 5,871,944 | all 44,824 rational canonical Frobenius orbits in Q1421 |

The transported source W24 and normal-weight-four policies are forward
images of their named source sets; the W24 pullback is the inverse-route
image of the descendant-native set. The degree is coprime to the subgroup
order, so transport preserves the number of subgroup points and signed
classes. The normal-weight-four source has 44,824 potential
signed-Frobenius columns. For its transported image the corresponding action
is conjugated through the route; coordinate Frobenius on the exact
descendant is a different operation. Effective columns for the selected
W24 prefixes remain to be determined by the relation-matrix policy.

The accepted scalar stream contains 65,536 distinct nonzero scalars from
131,193 counter attempts under the [frozen query law](PROTOCOL.md). Its
17-byte-big-endian scalar SHA-256 is
`80696fed2af40d2d8247f5331f7592a4e9465334050a92b752654e3c987eeb81`.
Each public-point row hashes source affine `x,y` followed by descendant
affine `x,y`, each coordinate a 17-byte little-endian polynomial-basis
integer. The 16-, 256-, and 65,536-row paired digests are respectively
`9d2a94382e7bde309697024ef0c54f941e28eb3dad5c1bc08bdcaec89b25ab9f`,
`f1a3fcf920273dbe4f0da51a4a42a55703a5bd40a0edcc3ca897ef455ca9890e`,
and the full digest above. The source-only and descendant-only full digests
are in the manifest and [full verification receipt](runs/R1/batch65536/verification.json).

## Construction and independent replay

The [input producer](freeze_inputs.py) scanned both complete W24 gzip
archives, checked their compressed and raw SHA-256 digests and monotone
mask order, and fixed each first-5,871,944-mask prefix. The
[independent input replay](verify_inputs.py) reconstructed all prefix and
control selections and all 65,536 accepted scalars without calling the
producer. Both source and descendant W24 prefixes had 64 fixed point
controls, and Q1421 contributed 128 fixed normal-weight-four controls.

The [direct point producer](point_stage_sage.py) reconstructed the exact
forward and dual degree-263 maps in checked Sage, checked all 256 fixed
factor-base points and route round trips, and derived public queries by
scalar multiplication on both curves for the 16- and 256-query prefixes.
The [independent pilot verifier](verify_points_sage.py) repeated those
controls and built the same public points with batched binary-power sums.
It checked the one-target workload and direct scalar/map identities on its
fixed query samples.

The exact descendant has an `a4` term. For bulk additions, both full-stream
implementations use the isomorphic normalized curve
`y'^2 + x y' = x^3 + (a6 + a4^2)` with `y' = y + a4`, then convert results
back to the exact descendant. The [full producer](batch_points_sage.py)
uses 33 radix-16 fixed-base tables; the
[independent full verifier](verify_batch_points_sage.py) sums 130 binary
powers. It rebuilds the field, route, generators, scalar law, and primary
target, then checks 80 direct scalar/forward/dual-map samples. Both
implementations matched every ordered point digest under the frozen
1,800-second, one-worker, 4 GiB envelope.

| Execution | Recorded status | Queries | Wall s | CPU s | Peak RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: |
| Direct pilot producer | `PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS` | 16 | 67.008 | 64.992 | 332.2 |
| Independent pilot replay | `PASS_INDEPENDENT_PUBLIC_POINT_REPLAY` | 16 | 71.804 | 65.327 | 354.4 |
| Direct screen producer | `PASS_PUBLIC_POINTS_AND_ROUTE_CONTROLS` | 256 | 93.305 | 80.538 | 275.5 |
| Independent screen replay | `PASS_INDEPENDENT_PUBLIC_POINT_REPLAY` | 256 | 103.198 | 81.284 | 354.2 |
| Radix-16 full producer | `PASS_BATCH_PUBLIC_POINT_STREAM` | 65,536 | 62.886 | 60.537 | 449.0 |
| Independent full replay | `PASS_INDEPENDENT_FULL_PUBLIC_POINT_STREAM` | 65,536 | 448.114 | 185.772 | 453.9 |

These wall times are construction and verification diagnostics on a host
without the required CPU-isolation receipt. The full producer's exclusive
recorded phases are 24.128 seconds for source and route setup, 3.719 and
3.988 seconds for the two radix-16 point batches, and 31.051 seconds for
encoding, digests, and 80 direct checks. The independent replay's larger
wall/CPU gap records host contention. No target-dependent IC online timing
occurs in this input gate.

## Next decision

The public inputs and point transport satisfy the gate for a paired
six-summand PDP screen. Freeze a compact normal-weight-four descent encoding
and a matched source-W24 control on the first 16 and 256 ordinary query
points before inspecting relation yield. Record every attempt status,
verified relation, novel rank row, and charged solver cost. Advance to the
65,536-query rank trajectory only when that screen demonstrates useful
independent relations; then build the final matrix, solve it, and time the
one-target descent against the same-point rho reference. This result fixes
the input and route stages; the PDP policy, relation collection, matrix
solver, and target descent remain unspecified, so `candidate_id` stays null.
