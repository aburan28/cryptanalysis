# ECC2K-130 degree-263 route and exceptional-point replay

This directory freezes one oriented degree-263 isogeny from the public
ECC2K-130 Koblitz model over `GF(2^131)` to a descending binary curve. Its
route ID is `IW1E263d1hadee4e69fa3d`. The exact field, curve IDs, generator,
kernel polynomials, ordered edge, dual, and subgroup transport certificates
are in `ecc2k130_degree263_route_manifest.json`; the catalog graph in
`../ic-candidate-catalog/isogeny_routes.json` points to that artifact.

The source endomorphism order has conductor 1: its `F_2` Frobenius trace is
`-1`, giving the fundamental discriminant `-7`. The saved degree-263 kernel
is not `F_2`-stable (its monic polynomial has coefficients outside `F_2`),
and its codomain has `j != 1`. The split-prime horizontal kernels of the
maximal order are `F_2`-stable; this edge therefore descends to conductor
263 and has `V263L0 -> V263L1`. The conductor of the `F_(2^131)` Frobenius
order is recorded separately. The route does not carry the Koblitz curve's
cheap degree-2 Frobenius endomorphism to the descendant.
The horizontal/descending classification uses the ordinary-volcano theorem
in [Sutherland, *Isogeny volcanoes*](https://arxiv.org/abs/1208.5370).

The original checked replay reconstructs both 263-isogenies from their
degree-131 kernel polynomials, verifies their source and target subgroup
points, and checks that the oriented dual composition is `[263]` on the
generator and one public-point fixture. The new exceptional-input replay
checks infinity, rational order-two torsion, and **every nonzero point in
both kernels**. Each kernel has 131 distinct `x` roots over the base field;
each root lifts to two points over the quadratic extension, giving 262
nonzero points per map. All 262 map to infinity under the guarded evaluator.
The `y` equation has trace one for every root, so no nonzero kernel point is
rational over `GF(2^131)`. The guarded evaluator also agrees with Sage on the
generator and public-point fixture over the base field and quadratic
extension, including the dual composition.

The accepted Sage 10.10.rc0 runtime's raw Kohel `_eval` raised
`ArithmeticError` on a sample point from each kernel because its affine
denominator vanishes. `degree263_transport.evaluate_with_kernel` first
recognizes infinity and kernel roots, returns the codomain identity there,
and uses `_eval` on ordinary points. This is a correctness guard for the
complete group map; the raw exception does not invalidate the isogeny.
The frozen replay receipt and checked Sage runtime record are kept beside
the scripts. They are correctness evidence and unisolated stage costs, not
CPU speedup measurements.

`candidate_id` remains `null`: the route alone is not a complete index-
calculus candidate. No factor-base rank, natural PDP relation yield,
single-target DLP recovery, matrix solve, or paired rho speedup is claimed.
The next experiment must compare equal **usable** factor-base sizes on the
source, descendant-native, transported, and pullback constructions with
held-out target points and fully charged target-dependent work.

From the repository root, inspect the frozen artifacts and run an
independent exceptional replay to a new output path:

```sh
python3 experiments/koblitz-polynomial-w-pair-20260925/verify_ecc2k130_263_route_manifest.py
python3 -m unittest discover -s experiments/ic-candidate-catalog -p 'test_*.py'
./sage --runtime-info > /tmp/ecc2k130-degree263-runtime-info.json
./sage -python experiments/koblitz-polynomial-w-pair-20260925/sage_verify_ecc2k130_263_exceptional.py \
  --out /tmp/ecc2k130-degree263-exceptional-replay.json
```

The replay refuses to overwrite an existing output path. The constructor
scripts reproduce the forward and dual frozen controls; the static verifier
checks their content hashes, curve and route IDs, registry links, and the
exceptional receipt. `build_ecc2k130_263_route_manifest.py` deterministically
regenerates the manifest from those frozen controls and the replay receipts.
