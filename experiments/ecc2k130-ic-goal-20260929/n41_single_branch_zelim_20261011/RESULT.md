# Derived-output preflight exposes a serialized-clause failure

The exact substitution `Z=S+w²+w` removes three independent 41-bit
four-atom output vectors from the affine-shear N41 public circuit. Its
complete archived public-witness assignment passes all 299,273 CNF
clauses and 61,440 native-XOR rows. The first solver invocation then exited
immediately with **`PRODUCER_FAILURE`**: a derived `Z` bit equal to constant
zero was written as an interior `0` in a nonzero-field clause. In DIMACS,
that token ended the clause early and CryptoMiniSat reported a parse error
before search began. The runner's generic fallback labeled its
[query receipt](query_result.json) `BOUNDED_UNKNOWN`; the
[failure classification](failure.json), raw [stderr](solver.stderr.gz),
and [stdout](solver.stdout.gz) preserve the actual status and formula hash.

The [frozen protocol](protocol.json) binds the N41 public target
`(1458168294740,1672312028033)`, source and solver hashes, one worker,
60-second solver flag, five-second parent margin, and 4 GiB RSS.
The [field replay](audit_result.json) checks the shared sheared quartic on
sixteen inputs. The failure is a serialization error, not evidence about
the mathematical source or solver yield. A separately frozen
[corrected variant](../n41_single_branch_zelim_v2_20261011/RESULT.md)
normalizes constant bits before emitting nonzero clauses and explicitly
classifies parser failures.
