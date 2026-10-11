# Planted-witness localization after the v1 W24 SAT control failure

The first six-summand W24 SAT control reached 100,002 conflicts without a
model. Its exact formula has SHA-256
`2e2748a557e1ca7a1773ee14fedc910410db7bf2c1dda2ab076ae9c248fba877`.
This follow-up is restricted to the **same planted group relation**. It does
not relax the v1 rule that forbids a natural-target run after the unresolved
control, and it cannot estimate ordinary decomposition yield.

Derive the six masks and minimum-encoded-y raw points from the same published
source controls. Reconstruct each of the six exact inverse witnesses
`v_i=1/w_i` and the four u coordinates of the successive raw partial sums
after 2, 3, 4 and 5 points. Check all five S3 identities directly in the
field. Build the same pinned-mask/fiber formula as v1, then add **only unit
clauses** for one of three predeclared witness classes:

1. `both`: pin all six 131-bit inverse witnesses and all four 131-bit S3
   intermediate u values. This must yield a Sage-verified SAT model before
   interpreting any search comparison.
2. `inverse`: pin the six inverse witnesses only; leave intermediate u values
   to the solver.
3. `intermediate`: pin the four intermediate u values only; leave inverse
   witnesses to the solver.

Execute in that order with the same CryptoMiniSat 5.14.7 binary, one worker,
seed zero, 100,000 conflicts, 30 seconds, and monitored 4 GiB RSS cap per
variant. Stop after `both` if it does not produce an independently replayed
valid SAT model. Preserve every result, including `INDETERMINATE`, timeout,
OOM and invalid models, with formula and solver-output hashes, source hashes,
field/group checks and resource counts. Use the checked repository Sage
launcher and save `--runtime-info` before each run.

If only `inverse` succeeds, missing inverses are the dominant obstruction at
this bound; if only `intermediate` succeeds, missing partial-sum values are.
If both single-class variants fail but `both` succeeds, the bound cannot
separate the two search costs. A fast `both` result demonstrates only that
the XCNF admits the planted witness; it does not establish solver coverage
or an IC relation on the frozen natural target. All timings on this
unisolated host remain exploratory stage diagnostics.
