# Q1424 four-leaf S3 solver parameter screen

## Contribution

This screen holds the complete four-variable-leaf S3 formulas, exact bases,
and ordinary public targets fixed while changing CryptoMiniSat search
parameters. It measures whether solver configuration alone can expose an
ordinary four-point relation without shrinking the relation supply as Q1423
does. The source, binary, inputs, grid, and caps are hashed before timing.

Q1424 is a stage proposal: `candidate_id: null`, `run_id: null`, and
`isogeny: none` (`ISO0`). It does not assign a complete IC candidate ID.

| Degree | Curve ID | Exact base | B before folding | K after sign/Frobenius folding | Ordinary workload |
| ---: | --- | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | Q1301 W≤3 subgroup x-orbits | 24,062 | 227 | `74f2979b3e68` |
| 83 | `EC1N83Ckb1h876c2921cb64` | Q1325 cofactor-projected W≤5 | 30,977,592 | 186,612 | `bab50a1e5f66` |

N53 reuses `n53_ordinary_exact_base_orbit.xcnf.gz`: four exact subgroup orbit
leaves and three factored S3 links. N83 reuses
`n83_q1404_ordinary.xcnf.gz`: four raw W≤5 leaves, three factored S3 links,
and the four-preimage target selector. Both archives already contain a
complete public point-decomposition query. Each solver variant first solves
the corresponding Q1419 locked control to test its XCNF/flag compatibility.

The grid is: baseline, seed17, polarity false, polarity random, geometric
restarts, Luby restarts, pure VSIDS branch schedule, and wider active XOR
Gaussian matrices. All eight run on N53. Baseline, seed17, Luby, and wide
Gaussian run on N83. Settings are compared on the same public target and
formula at a fixed bound of 200,000 conflicts, 45 solver seconds, 55 external
seconds, one thread, and 1,536 MiB sampled RSS. The locked control has 10
solver seconds and 15 external seconds. Output states are SAT, UNSAT,
BOUNDED_UNKNOWN, and PRODUCER_FAILURE; every state is archived.

The relevant quantity is verified natural relations and, if any are found,
conflicts and complete stage cost to that relation. Conflicts, decisions,
wall time, propagation, memory, and Gaussian statistics are diagnostics; a
smaller conflict rate or faster censored run is not an IC speedup. An ordinary
SAT assignment must satisfy all serialized CNF and XOR rows, lift to four
points in the exact base, and add to the public target. New ordinary relations
need independent checked-Sage replay and rank novelty before promotion.
The host lacks a CPU-isolation receipt, so wall-time comparisons remain
exploratory. A complete N131 field-operation `2^x` estimate requires ordinary
yield, useful rank, collection, matrix, descent, and replay measurements.
