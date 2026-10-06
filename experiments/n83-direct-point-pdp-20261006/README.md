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

The initial sandboxed launch is retained as a
[harness failure](runs/pinned_planted_f0_v1/harness_failure.json): macOS
denied the watchdog's process-tree inspection, so its orphaned solver group
was killed and the attempt is not treated as resource-valid. The repaired
watchdog passes a fail-closed regression control. The
[valid pinned-mask run](runs/pinned_planted_f0_v2/receipt.json) built a
610,956-variable, 1,766,030-CNF-clause, 22,201-XOR-row circuit in about
1.75 seconds and returned `BOUNDED_UNKNOWN` after CryptoMiniSat's 120-second
internal limit. The complete process-tree interval was 138.05 seconds with
551 MB sampled peak RSS. There was no model or UNSAT proof.

The next [frozen diagnostic](sign_enum_protocol.json) enumerates all 32
lift-sign assignments in a public, fixed order on the *same pinned-mask
circuit*. It does not use the private sign witness to choose an assignment.
Each branch receives explicit sign-unit clauses and a bounded solve. A found
model still needs complete XCNF verification, group replay, and independent
Sage replay. This diagnostic can determine whether five sign choices caused
the pinned-mask solver to wander through auxiliary variables; it is not
an unpinned factor-mask search.

The [sign-enumeration receipt](runs/sign_enum_v1/receipt.json) records 18
attempted branches in 13.915 seconds of exploratory complete-run wall time:
CryptoMiniSat reported 17 UNSAT branches and one SAT branch. The SAT model
passed every CNF clause and XOR row, integer-field group replay, and an
[independent checked-Sage replay](runs/sign_enum_v1/sage_replay.json). Sage
verified the exact factor-mask weights, all five curve points, measured
factor-base orbits, four regular additions, raw fiber, and subgroup target.
The branch order was fixed before execution and did not use the private sign
witness. Solver-reported UNSAT branches have no independent proof
certificates; their compressed raw stdout logs and hashes are archived.
The SAT model stdout remains local because it contains the planted witness.

This is a **passed pinned-mask positive control** for the direct-point
encoding, not a solved natural PDP. It isolates a practical SAT-search
problem: with five sign bits implicit, the same pinned-mask circuit timed
out, while explicit sign assignments reduced each branch to a deterministic
arithmetic check. The next gate is an unpinned planted search, followed by
ordinary public fibers only if that search succeeds and exceptional paths
are accounted for. No IC speedup follows from this control.

The unpinned planted and ordinary runner paths read only the identical
public fixtures, measured representatives, solver binary, and protocol.
The local private fixture is opened only for the explicitly pinned planted
mode; an unpinned receipt records its private-fixture input as `null`.

The first [public-only unpinned planted attempt](runs/unpinned_planted_f0_v1/receipt.json)
used raw fiber 0 with all five factor masks and signs free. It built a
610,956-variable circuit with 1,765,615 CNF clauses and 22,201 XOR rows.
CryptoMiniSat returned `BOUNDED_UNKNOWN` at its 120-second internal limit;
the bounded process-tree interval was 136.214 seconds with 572 MB sampled
peak RSS. No witness or UNSAT proof was produced. The receipt's inherited
claim-boundary sentence mentions a pinned result, but its mode and inputs
identify this as an unpinned attempt; neither supports a natural-yield or
speedup claim.

The [next frozen diagnostic](unpinned_sign_enum_protocol.json) enumerates
the same 32 public-order sign branches with every factor mask still free.
It charges every attempted branch under a 600-second whole-run cap and a
2 GiB process-tree RSS cap. A solved branch must pass full XCNF and group
replay and independent checked-Sage replay before it qualifies as a planted
control. If the bounded attempt remains unresolved, ordinary-query yield
and a complete IC pipeline remain unmeasured.
