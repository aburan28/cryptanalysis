# Q20261010125300: bounded chained-S3 SAT parameter sweep

The experiment compares six CryptoMiniSat configurations on the archived,
exact balanced-S3 XCNFs for the Q1410 N53 ordinary target, Q1408 N83
ordinary target, and Q1408 N83 satisfiable control. Each formula has four
sparse normal-basis leaves, two pair-intermediate coordinates, and the
cofactor-preimage target selector. It never expands S5. The N53 base is
Q1301 W≤3 on `EC1N53Ckb1hf77aab617904`, with actual `B=24062` and
`K=227`; the N83 base is Q1325 W≤5 on
`EC1N83Ckb1h876c2921cb64`, with actual `B=30977592` and `K=186612`.
Their enumerated-set digests are frozen from the Q1419 profile. The stage
is proposal Q20261010125300, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"` (`ISO0`).

Freeze the three compressed XCNFs, Q1419 profile, solver executable,
source files, flags, and fixed cell order before running. Every cell uses
one solver thread, seed 0, a 200000-conflict internal cap, and a 30-second
external wall cap. Run all 18 cells once, preserving stdout, stderr,
return code, conflict count, wall time, and peak child RSS. Classify exit
code 10 as SAT, 20 as UNSAT, and a cap or timeout as `BOUNDED_UNKNOWN`;
never infer UNSAT from a capped run. Include solver process and formula
loading in exploratory wall time. Formula decompression is reported
separately. No host-isolation receipt is available, so wall comparisons
remain exploratory.

Configurations are default; Gaussian reasoning with a 10000-column budget
and automatic disabling off; VSIDS branching; VMTF branching; geometric
restarts; and Luby restarts. This is a coarse bounded parameter search.
Promote a setting only if it returns a verified ordinary relation, or if a
follow-up controlled experiment confirms a reproducible improvement. A
known-satisfiable N83 result validates solver behavior but does not
estimate ordinary relation yield. If a SAT model appears, check every
serialized CNF and XOR row and replay the exact point sum before treating
it as a relation; a newly found N83 ordinary relation also needs a checked
Sage replay. A full `IC1` candidate and N131 solve exponent require
relation collection, rank, final matrix, and target-descent records.
