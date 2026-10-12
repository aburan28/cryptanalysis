# XYZZ accumulator for the radix-152 fixed-generator format

The opt-in XYZZ evaluator preserves the radix-152 tables and selected
point stream while replacing the Jacobian accumulator. The ordinary
nonexceptional mixed-add formula uses **8 field products and 2 field
squares**, versus **8 products and 3 squares** in the merged Jacobian
evaluator. Both retain the same 69,698 affine table points and report
4,568,960 retained table and atlas bytes. The XYZZ accumulator uses its
existing Solinas unit rotation and binary affine recovery.

The candidate changes exactly three evaluator expressions in a disposable
copy of the merged native source. The [builder](native_overlay_xyzz.py)
records both compiled-module hashes and the transformed included-source
hash. Its first development invocation stopped before compilation because
the evaluator lives in an included file rather than the parent module; the
builder was corrected before the [source freeze](PROTOCOL.md) at
`f8aa39e7e`. The first new-panel replay exposed a portability issue in
the receipt: the generated module hash included an absolute `include!`
path. The [initial receipt](replay-path-bound.json) is retained. The
checker was revised to bind portable included-source hashes, then frozen
with the second new-panel generator at `67cbfc7e8` before that draw.

| Source-frozen replay | Development control | First new holdout | Second new holdout |
| --- | ---: | ---: | ---: |
| Public secp256k1 scalar cases | 512 | 512 | 512 |
| Reference, XYZZ, and independent points equal | 512 | 512 | 512 |
| Recorded noninitial additions | 8,704 | 8,704 | 8,703 |
| Unit rotations | 1,022 | 1,022 | 1,023 |
| Retained table and atlas bytes | 4,568,960 | 4,568,960 | 4,568,960 |

The new panel uses seed `20261012231` and has fixture SHA-256
`c6137082fad14b80c530796412ed94ca61b43ebcf2034a64e16cf0898affeb58`.
An independent projective binary multiplier generated every expected
point. The new point stream has SHA-256
`e266e14019e2a3728c44a5628dab5f90955911769549fd57bea3b065aac1cf97`.
The second new panel uses seed `20261012232`, fixture SHA-256
`526f6bdf2efee619f97a79a660ac7ca9ad6240f455ab36b1f72f7e95e15b1825`,
and independently generated point-stream SHA-256
`aab3be12aa3767f72a27879b19c83f3b888dcdb752240b05ac976f4bc38fa651`.
The [portable replay receipt](replay.json) binds both source overlays, all
three input files, output rows by digest, and exact operation counts. The
[local build receipt](local-build.json) records both macOS ARM64 release
binary hashes, generated-module hashes, and Rust 1.93.1.

The one-square saving applies to each ordinary nonexceptional addition;
the replay records selected terms but does not instrument exceptional
branches. A paired complete-operation run on a qualifying isolated host
will decide whether the changed coordinate path improves online CPU time,
including recoding, lookup, unit action, affine recovery, and verification.
The inherited radix-152 [proof map](../prime-j0-axis152-20261012/PROOF.md)
covers scalar reconstruction and table reachability.
