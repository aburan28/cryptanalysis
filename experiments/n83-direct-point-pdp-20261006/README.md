# N83 deterministic point-circuit PDP pilot

This experiment tests a different five-summand decomposition encoding on
`EC1N83Ckb1h2bcb59d56ad6`. The [earlier W3/W4 S3 SAT gate](../hamming-ic-e2e-20260929/N83_W34_SAT_GATE.md)
did not solve when the five factor masks were pinned but three intermediate
x-coordinates remained unknown. It solved quickly when those intermediates
were pinned too. That observation motivates computing all intermediate
points *deterministically* from factor-mask and sign choices.

The [frozen protocol](protocol.json) uses the same exact public planted and
ordinary points as that earlier gate. The checked-Sage fixture producer was
rerun; its public bytes have exactly the same SHA-256 as the original.
The [regeneration receipt](runs/regenerated_fixture_v1/fixture_regeneration.json)
also checks that the planted five-point sum is in the circuit's regular
affine-addition locus. The private witness stays ignored.

For each factor, [the circuit](direct_point_circuit.py) converts a normal
mask to x, computes x inverse by an addition chain, uses half-trace plus one
sign bit to obtain y, and enforces the curve equation. Four deterministic
affine additions produce a raw point constrained to one exact target fiber.
The circuit explicitly requires every factor x and every addition
denominator to be nonzero. It therefore covers only the regular locus; it
is **not** a complete point-decomposition algorithm until equal-x,
doubling, inverse-pair, and identity paths are covered and verified.

The [small-field control](test_direct_point_circuit.py) solved all four
lift-sign combinations of a selected pair over `GF(2^5)`, decoded each SAT
model as an independently checked group sum, and proved an unattainable
target UNSAT for the same fixed factor x-values. This checks the exact
XCNF arithmetic on a nontrivial toy instance, not N83 search performance.

The first N83 gate pins only the five factor masks and chooses their correct
raw fiber. The sign bits, point lifts, and all intermediate points remain
unassigned to the SAT solver; the circuit computes them. The
[bounded runner](bounded_direct_point.py) enforces the 900-second process-tree
wall and 2 GiB RSS caps over build, serialization, solver, and verification.
It preserves a receipt on timeout, OOM, or runner failure. A SAT result must
pass every CNF/XOR row, independent integer-field group replay, measured
factor-base orbit membership, and then a separate installed-Sage replay.

Only a passing planted control justifies unpinned planted attempts. Only a
passing unpinned control and exceptional-case accounting justify ordinary
public-target fibers. Every attempted branch must retain its cap and
failure status. No complete IC candidate ID, natural relation yield,
factor-log matrix, one-target DLP, same-point rho comparison, or speedup is
claimed by this design and control stage.
