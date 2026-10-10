# XYZZ accumulator for the fused orbit-tau scalar format

This candidate keeps the nineteen-window Eisenstein recoder and fused `P`/`tau(P)` cube-root table from the parent branch. It changes the online accumulator to XYZZ coordinates, allowing each ordinary affine table-point addition to use **8 field multiplications and 2 squarings**. The parent Jacobian path uses 8 multiplications and 3 squarings. Both formats retain the same 5,726,228-byte table and accept public scalars through separate opt-in CLI modes.

An XYZZ tuple `(X,Y,ZZ,ZZZ)` represents `(X/ZZ,Y/ZZZ)` with `ZZ^3=ZZZ^2`. For a mixed addition with affine `(x2,y2)`, the implementation computes

`U2=x2*ZZ; S2=y2*ZZZ; P=U2-X; R=S2-Y; PP=P^2; PPP=P*PP; Q=X*PP;`

`X'=R^2-PPP-2Q; Y'=R*(Q-X')-Y*PPP; ZZ'=ZZ*PP; ZZZ'=ZZZ*PPP`.

These are [Sutherland's XYZZ mixed-addition formulas in the Explicit-Formulas Database](https://hyperelliptic.org/EFD/g1p/auto-shortw-xyzz.html). Equal points use its doubling formula; inverse points return the identity. The final conversion inverts `ZZZ` once, derives `1/Z = ZZ/ZZZ`, and computes the affine coordinates. This preserves the exact scalar identity established for the fused orbit-tau table.

The source tests compare 128 chained XYZZ and Jacobian additions, check `ZZ^3=ZZZ^2` after each, cover equal and inverse inputs, and compare the complete 4,096-scalar prior panel with the parent mode and independent binary multiplication for its first 128 cases. After source freeze, `make_inputs.py` draws a disjoint 4,096-scalar panel, `make_fresh_fixture.py` computes independent binary points, and `run_fresh.py` replays both formats. `verify_fresh.py` checks the source and complete output streams. An exact wrapper-operation diagnostic and isolated wall timing are separate gates.
