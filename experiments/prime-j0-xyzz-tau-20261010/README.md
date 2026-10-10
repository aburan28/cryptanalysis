# Endomorphism and merge in XYZZ coordinates

For the deferred-tau scalar evaluation `B0 + tau(B1)`, this variant computes
the degree-three endomorphism directly on the XYZZ bucket and adds two XYZZ
points. It retains the same scalar recoding and two-X affine table as the
preceding bucket formats. Modes 151 (18 windows) and 152 (17 windows) keep
the earlier Jacobian merge modes selectable as controls.

Let `ZZ=Z²`, `ZZZ=Z³`, `W=(1−β)X`, `R=4Y²−3X³`, and `I=3X³−2R`, with
`β³=1`, `β≠1`. The projective endomorphism sends `(X,Y,Z)` to
`(R,YI,WZ)`, so its XYZZ image is `(R,YI,W² ZZ,W³ ZZZ)`. A direct XYZZ
addition then combines this image with the ordinary bucket. This removes a
coordinate conversion and avoids forming a Jacobian `Z` for the transformed
bucket.

The independent 4,096-scalar fixture and ten boundary cases are frozen in
`prime-j0-tau-bucket-two-x-20261010`. `run_replay.py` checks both new modes
against each expected point; `verify.py` binds the source commit, fixture,
binary result hashes, and every output. The temporary `ops-diagnostic.patch`
counts calls to native field-operation wrappers on the same scalar panel;
`verify_ops.py` reapplies it to the frozen source and checks the raw totals.

| Format | Add | Subtract | Multiply | Square |
| --- | ---: | ---: | ---: | ---: |
| 17 windows, Jacobian merge | 90,110 | 486,789 | 569,328 | 143,356 |
| 17 windows, XYZZ tau | 90,110 | 486,789 | 565,232 | 143,356 |
| 18 windows, Jacobian merge | 94,207 | 516,260 | 602,104 | 151,550 |
| 18 windows, XYZZ tau | 94,207 | 516,260 | 598,008 | 151,550 |

The XYZZ path saves one field multiplication per scalar for each window size.
Retained table sizes remain 6,615,956 bytes for 17 windows and 3,994,692
bytes for 18 windows. These are operation-count diagnostics; a CPU wall-time
comparison requires a passing host-level isolation receipt under
`docs/ISOLATED_BENCHMARKS.md`.
