# Planted-only XCNF witness audit after the functional-S3 timeout

The preregistered functional W24 planted control produced XCNF SHA-256
`1e12c05b798af29e5ccbde939a618caffcd4b5605a19111b6153a0aaff136e6a`
and timed out at the strict 30-second process limit without a model. This
follow-up cannot reopen the ordinary-target gate. It tests whether the exact
archived XCNF admits the known planted group witness despite the solver
failure; it does not measure natural PDP yield or an IC speedup.

Use the same first six source control masks, minimum-encoded-y raw points,
and selected cofactor-four fiber. Compute the four partial sums independently
with standalone field/group arithmetic. For each partial-sum `u`, evaluate
both numerical roots of the already committed complete S3 quadratic and
record the root bit matching the group sum; select bit zero when both roots
coincide in an exceptional branch. Assign only the two fiber bits, six sets
of 24 mask bits, and four root-choice bits as primary inputs. Instrument the
committed circuit class so every AND and XOR gate computes its output truth
value from earlier wires while building exactly the same formula. Use a
300-second build bound and 4 GiB builder RSS check. Emit one packed truth bit
per variable, the raw XCNF hash, source hashes and a saved checked-Sage
runtime receipt. Stop if the rebuilt XCNF is not byte-identical to the
strict-run archive.

An independent verifier must read the *archived* raw XCNF and packed witness,
without importing the circuit builder, and check the header, every CNF clause,
and every native-XOR row under CryptoMiniSat's XOR-literal parity convention.
Preserve the assignment, counts, exact failures, and verifier receipt. A PASS
proves satisfiability of this one planted formula; it does not imply the
bounded solver can recover a witness or that ordinary-target relations exist.
A failure remains an encoding defect or unverified artifact, not an UNSAT
result. All wall timings are exploratory on this unisolated host.
