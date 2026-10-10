# Binary-GCD affine finalization for Eisenstein U14 scalar multiplication

The opt-in mode converts the final Eisenstein Jacobian point to the
four-limb secp256k1 Montgomery field and replaces the field's fixed
`p-2` inversion chain with binary extended GCD. The parent path uses
257 squarings and 14 other four-limb products for inversion. This path
uses shifts, modular additions and subtractions, followed by one
Montgomery correction product. Scalar decomposition, U14 table selection,
unit actions, and point additions share the hybrid parent's code.

The correction follows from the stored value `zR'`: binary GCD returns
`(zR')^-1`, so a Montgomery product with precomputed `(R')^3` returns
`z^-1 R'`, the inverse in the field representation used by the affine
step. The modular-half operation retains the carry from `x+p` when `x`
is odd. This mode has input-dependent branches and stays opt-in for
public-scalar research.

## Correctness record

The native release suite passed **74/74** tests. The new inverse test
checked modular halving on six boundaries and 512 deterministic field
elements, compared every nonzero inverse with the parent's exponentiation
chain, and verified `a*a^-1=1 (mod p)`. The complete point comparison
matched parent and candidate on 21,004 boundary, prior-panel, and
disjoint new scalar cases. The first 128 new points also passed independent
binary scalar replay. Both modes passed all 129 frozen secp256k1 fixture
points. The [verification receipt](verification.json) binds source, input,
binary, native test log, fixture outputs, and exits. The release binary
SHA-256 is
`8a435cb9af680673351d9f195277cc020846ca81e161944dd90ae81510a87aa1`.

The 4,096-scalar holdout was generated after protocol commit `acbd9faad`
with seed `20261010524`; its scalar digest is
`7a21805cdd086f13aeb0ee1663d57ad2b316efe55f1eb3091c7d4af99d599cc5`.
The x86-64 Linux release cross-compilation check passed with Rustup's
installed target; physical x86 execution remains a separate gate.

## Paired measurement

The [isolated manifest generator](make_isolated_manifest.py) pairs modes
123 and 124 on nine frozen fixture indices for five repetitions. The
online interval includes scalar work, point arithmetic, representation
conversion, inversion, affine formatting, and expected-point verification.
A controlled wall-time comparison awaits a physical host passing the
repository's isolation and noise gates. The existing serial RunPod queue
can provide x86 correctness replay while its containerized host fails the
strict CPU-isolation preflight.
The local manifest structure check emitted nine cases and five repetitions
with digest `1698f44f0c504d21c940aeb006d4dd4519af4883ddf37b51eea2e52d02964fa5`;
its CPU and NUMA identifiers were placeholders.
