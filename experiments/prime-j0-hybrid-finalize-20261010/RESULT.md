# Four-limb finalization of Eisenstein projective scalar multiplication

The opt-in U14 mode converts the final Jacobian point from balanced
Eisenstein Montgomery coordinates to a four-limb secp256k1 Montgomery
field, then performs inversion and affine formatting there. Scalar
reduction, the fixed-limb Voronoi selector, table selection, unit actions,
and point additions use the parent mode's code path.

The conversion is `z*2^256 = a*2^128 + b*beta*2^128 (mod p)`, where
`a+b*beta = z*2^128 (mod p)`. Field constants are initialized before the
online interval. The finalizer uses six fixed-constant products for the
three projective coordinates, the fixed `p-2` inversion chain, four
products for `Z^-2`, `Z^-3`, `X/Z^2`, and `Y/Z^3`, then two Montgomery
exports. It avoids arbitrary-precision decimal conversion at this output
boundary.

## Correctness record

The native release suite passed **72/72** tests. The new tests checked
400 signed coefficient pairs, including coefficient boundaries, against
the independent BigInt field mapping. They compared the parent and hybrid
finalizers on 16,908 boundary, prior-panel, and disjoint new scalar cases;
the first 128 new points also passed independent binary scalar replay.
Both modes passed all 129 frozen secp256k1 fixture points. The
[verification receipt](verification.json) binds the inputs, source, binary,
test log, fixture output, and exits. The release binary SHA-256 is
`66767e41439480957df57d32dd6b9eddc1c6ee816cc75237b96a20edea29d2c3`.
The x86-64 Linux release cross-compilation check passed with the installed
Rustup stable target; this check did not execute the binary on x86 hardware.

The new 4,096-scalar holdout was generated after protocol commit
`c0b12d0f1` with seed `20261010423`; its scalar digest is
`5aeb213f6339077c55dfdde0c35a5762a0422373c977d99929cbf784e1a8d975`.

## Paired measurement

The [isolated manifest generator](make_isolated_manifest.py) pairs the
parent mode and hybrid mode on nine frozen fixture indices for five
repetitions. Its timer charges reduction, scalar recoding, table lookup,
point arithmetic, representation conversion, inversion, formatting, and
expected-point verification. A controlled wall-time result awaits a
physical host that passes the repository's isolation preflight. The
existing RunPod container is assigned to serial x86 correctness replay;
its CPU topology cannot certify an isolated speedup.
The local manifest structure check emitted nine cases and five repetitions
with digest `352ba68749a59b8f5aa22b9bf547aa1dd1c03c8278c8f9483d68a830d57a6e83`;
its CPU and NUMA identifiers were placeholders.
