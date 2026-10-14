# XYZZ replay of the fourteen-window unit-orbit digit stream

Use every scalar in the existing 129-case
`tau6-comb13-bench-fixture.json`. For each scalar, select the same nearest
Eisenstein representative and unit-orbit digits as the native U14 format.
For every nonzero digit `(a,b)` at positional factor `2^s`, construct its
public addend independently as `[(a+b λτ)2^s]G` with the affine reference
arithmetic. Insert those addends into the XYZZ mixed accumulator and compare
the final affine point with both the independent fixture point and direct
reference scalar multiplication. Check the XYZZ invariant and progressive
affine sum after every addition.

Commit this protocol and `xyzz_u14_replay.py` before generating the result.
Retain the fixture, source, protocol, and result hashes; the exact input
digest; all 129 case statuses; generic and exceptional addition counts;
and the symbolic field-product count. This exercise validates the actual
digit/addend sequence for the coordinate formula. The precomputed table
entries and native arithmetic are validated separately in the U14 and
radix-943 receipts. The 11-to-10 product difference is a formula count;
online CPU timing remains subject to the host-isolation gate.
