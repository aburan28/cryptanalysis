# Last-use reclamation for independent algebraic proofs

The verifier counts future uses of every DAG node, including duplicate operands
and output references. It evaluates and validates every node, even an unused
one, then releases a polynomial after its last use. Outputs remain pinned until
their equality checks. All original-equation derivation, reverse inclusion,
reducedness and Boolean completion obligations remain required for acceptance.
The checker keeps independent hash-set polynomial arithmetic; producer code and
packed input transport are unchanged. The default remains the baseline checker.

Four explicit policies exist: `baseline` executes round93 unchanged; `keep`
instruments retention without releasing values; `release-cumulative` reclaims
values but retains the old cumulative term limit; `release-live` applies that
limit to simultaneously live proof terms. Live mode changes resource semantics;
an answer available only under it is not evidence of a speedup at equal budgets.
The live limit counts a newly constructed result before its parents are released.
A failed admission can therefore report a peak demand greater than its limit.
The limit is not an allocation preflight: the original arithmetic constructs a
result before its term count is known. It is not a process-memory cap.

`retained_terms` continues to count cumulative admitted terms. Separate counters
record peak live proof terms, live terms before cleanup, released terms/nodes,
planning work and metadata bytes. They exclude original equations, candidate
basis, set buckets, allocator metadata, transient reduction scratch, and the
vector of empty node objects that remains sized to the DAG. No RSS claim follows.
Use counts take four bytes per node; the public shape limits prove they fit in
32 bits, including repeated XOR operands and all outputs.

The additional topology pass is charged one logical unit per node and output.
Reference increments, release bookkeeping and deallocation are included in wall
time but not individually calibrated as hardware operations. Successful
arithmetic counters must match baseline after subtracting the explicit planning
charge. Earlier topology validation may change the first error on malformed
proofs. All remaining work and retention limits, failed attempts and fallback
costs remain explicit. Live storage is call-local and never cached between inputs.

The frozen eight-arm panel preserves the 14 families and 28 subsequent inputs:
F4 and reused Macaulay each under baseline/cumulative-release/live-release, plus
the existing bounded F5B and native interpolation comparators. All algebra arms
use round93 completion-first checking. Matrix multiplier degree is one for
nonlinear inputs and zero for linear inputs. Two warmup orders precede eight
balanced observation orders. One control order runs on optimized and UBSan
builds. Complete algebra time includes fresh production, failed proposals,
checking, fallback, reclamation and basis/proof export. Input packing and reusable
layout preparation remain outside this interval. No curve/IC result is claimed.

An independent Python lifetime simulator checks shared children, duplicate uses,
unused valid nodes, pinned outputs and wide rings. A 64-variable proof chain
requires 65600 cumulative terms but only 128 simultaneously live terms; this is
a resource-policy control, not a difficult polynomial solve. Malformed unused
nodes, bad outputs, small work/retention limits and concurrent calls are covered.
Accepted bases/proofs are independently checked and applicable small rings also
pass an exhaustive oracle. Archived libraries are not executed by audits.

Local timing is exploratory without host-wide isolation. Qualified, aggregate
and online speedups remain null. GPU crossover, curve replay, hard regularity
and new asymptotic F6 claims remain outside this component experiment.
