# Corrected derived-output circuit searches the public N41 target

The exact relation `Z=S+w²+w` derives each four-atom output from its seed
sum and a free 41-bit branch witness. Coupled with the `T=S+Z` shear, the
complete public-target formula has **97,565 AND gates, 159,242 variables,
299,273 CNF clauses, and 61,440 native-XOR rows**. Its archived public
relation satisfies every equation and reconstructs each block output
exactly. The separately frozen one-worker query parsed correctly, entered
active search, and ended `BOUNDED_UNKNOWN` at the 60-second solver cap.

The [circuit](circuit.py) drops constant-zero bits from each nonzero-field
clause. The [runner](run.py) checks every emitted CNF clause for an interior
zero before invoking CryptoMiniSat and reports a parser rejection as
`PRODUCER_FAILURE`. Those changes repair the
[preserved first attempt](../n41_single_branch_zelim_20261011/RESULT.md),
whose solver exited before search. The [complete public control](control_result.json)
checks all clauses and native-XOR rows on the independently audited twelve
source points; the [field replay](audit_result.json) checks the emitted
quartic on sixteen inputs.

The exact curve is `y²+xy=x³+1` over `GF(2)[t]/(t^41+t³+1)`, subgroup
order `549756390943`, public target `(1458168294740,1672312028033)`,
actual factor base `B=384`, and 26 folded columns. The
[protocol](protocol.json) fixes the same target, source, one worker,
60-second solver flag with five-second parent margin, 120-second
construction cap, and 4-GiB RSS as the
[affine-shear query](../n41_single_branch_shear_20261011/RESULT.md).
The [query receipt](query_result.json) records 65.092 seconds from solver
launch through parent stop, 406 restart rows and about 283,000 conflicts
in [stdout](solver.stdout.gz), empty [stderr](solver.stderr.gz), and no
terminal SAT or UNSAT line. The [cross-variant audit](../n41_single_branch_shear_20261011/variant_audit.json)
binds source, formula, logs, phases, and status. These wall intervals are
exploratory on an unisolated host. The N131 relation and complete
single-target pipeline remain active gates; `candidate_id` is `null`.

Reproduce the non-Sage control with `python3.12 -B audit_horner.py` and
`python3.12 -B run.py control`; the frozen public query used
`python3.12 -B run.py query` after `freeze`.
