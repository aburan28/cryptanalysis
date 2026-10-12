# Native point-path edge controls

Freeze the updated Rust source, `make_edge_fixture.py`, and this
protocol before generating edge inputs. Use three nonidentity bases:
the secp256k1 generator and two deterministic scalar multiples.
For each base, use scalar values `0,1,2,3,4,7,8,n−1,n,n+1`, where
`n` is the subgroup order. Derive exact short representatives,
width-four digits, prepared seeds, point outputs, and operation
counts through the checked repository Sage launcher. Save its
`--runtime-info` receipt before execution.

The native binary must verify all 27 prepared seed points and all 30
scalar outputs, including the curve identity for `0` and `n`, and
match every saved operation count. It must exit nonzero on a mismatch.
The already-frozen 64-case fixture must still replay after the source
change. This is native correctness on these cases; scalar reduction
and recoding remain supplied by Sage. No CPU timing or novelty claim
follows. Exceptional Jacobian addition inputs require a separate
control before treating this as a complete general-purpose formula.
