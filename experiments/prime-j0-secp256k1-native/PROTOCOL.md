# Native 256-bit point-path replay

This standalone Rust experiment imports the repository's unchanged
`suite/src/ct_bignum.rs` and `suite/src/ecc/secp256k1_field.rs`. It
implements the endomorphism-assisted projective nine-seed chain,
three-image unit orbits, cached `Z²,Z³` Jacobian readdition, paired
`τ` stride, and final affine recovery. Its scalar reduction and
width-four recoding are initially supplied by a frozen Sage fixture;
the native scope is therefore the **point path**, not a complete
scalar-input implementation.

Freeze `make_fixture.py`, Rust source, and this protocol before
generating a fixture from the 64 cases in the already-frozen
`cached-projective-result.json`. Use the checked repository Sage
launcher and save `--runtime-info` before fixture generation. The
fixture records the base point, every prepared seed, every digit,
expected output, and the operation schedule. The Rust replay must
check every seed and output against those Sage values, and reproduce
the saved stride/addition/cache counts. It must exit nonzero on any
mismatch. Preserve source and fixture hashes and the exact build
command. No CPU wall-time result from a contended host is admissible
as a speedup claim; the isolated host gate still applies.

The native replay is a correctness bridge toward a full scalar
implementation. It cannot prove that recoding, setup, allocation,
or the field inverse make this candidate faster than a published
baseline. Academic novelty is also unproved.
