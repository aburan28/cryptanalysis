# Coset-aware three-representative scalar format

For scalar `k` in the secp256k1 subgroup, the fixed Gauss-reduced
endomorphism lattice supplies 25 equivalent coefficient pairs in the
same `5×5` neighborhood already inspected by the native shortest
representative routine. Sort them by Eisenstein norm, maximum absolute
coordinate, `a`, and `b`; retain the first three. The first must match
the existing shortest representative. Verify
`a+bλτ ≡ k (mod n)` for every candidate.

Compute the existing selective mixed-alphabet τ stream **once** on the
shortest representative. Compute the zero-τ-priority stream on each of
the three representatives. Choose the lowest complete one-use source
cost, with ties preferring shortest selective, then zero-τ ranks 0, 1,
and 2. The selected path pays its actual seed preparation. CPU timing
must charge all four recoders and the representative ranking. No
preparation cost is silently shared between different one-use bases.

The 64-case native fixture is already-inspected design data. An
unrestricted 25-representative diagnostic found 919 `M+S` of possible
source saving over the shortest-representative zero-τ selector, but
would require up to 50 recoders. The chosen three-representative rule
uses one selective and three cheap zero-τ recoders; on design data its
complete cost was 85,921 versus 86,405, saving 484 `M+S` across 24
cases. This is a design score, not fresh evidence or a CPU result.

Freeze this protocol, `screen_coset_representatives.py`,
`coset_selector.py`, `make_coset_fixture.py`, and
`validate_coset_selector.py` in a commit before generating
`coset-fixture.json`. Use the checked repository Sage launcher, save
`--runtime-info`, and generate eight new bases with 32 deterministic
scalars each. Exclude all prior scalar fixtures available on this
branch and cross-check the exact-radix sibling fixture separately.
Preserve every row and failure. The prospective source gate requires
correct reconstruction of every selected representative, an aggregate
source saving against shortest-representative zero-τ on the same new
inputs, and independent Sage recovery of every public point.

If the source gate passes, implement the same rank ordering and four
recoders natively. Verify all representative pairs, ordered action
streams, prepared points, operation recounts, and final outputs.
Compare complete one-use scalar operations on the identical inputs
against the shortest-representative zero-τ evaluator. Promote a CPU
claim only with a physical-host isolation receipt and noise gates.

Nearby lattice decompositions and endomorphism recoding have prior art;
the academic novelty of this combined choice is unproved. This is a
variable-time research method.
