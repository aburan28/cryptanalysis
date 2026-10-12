# Pre-protocol syntax and parser checks

These checks ran before `protocol.json` was frozen and are not measured
panel rows. They retain the original solver output.

| Input | Command suffix after pinned solver binary | Boundary | Observed status |
| --- | --- | --- | --- |
| N53 pinned | `-useWatchedLiterals -useWatchedMonomials -checkModel -model -cpu-lim=10 /private/tmp/q1527-n53-pinned.anf` | local smoke; no outer cap | `SATISFIABLE`, exit 10; original XCNF and group replay passed |
| N83 pinned | `-useWatchedLiterals -useWatchedMonomials -checkModel -model /private/tmp/q1527-n83-pinned.anf` | 20-second Python subprocess wall cap | `WALL_CAP`; no terminal SAT/UNSAT conclusion |

Both plain ANF inputs were decompressed from the corresponding archived
`formulas/*.anf.gz` files. The 20-second N83 cap was imposed by the parent
process; the child emitted no terminal status before termination.
