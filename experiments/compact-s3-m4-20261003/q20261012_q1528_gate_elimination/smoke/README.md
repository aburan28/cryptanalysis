# Pre-protocol syntax and model-reconstruction checks

These checks ran before `protocol.json` was frozen. They retain raw output
but are not counted as measured panel rows.

| Input | Frozen solver binary flags | Boundary | Outcome |
| --- | --- | --- | --- |
| N53 pinned | `-useWatchedLiterals -useWatchedMonomials -checkModel -model` | 20-second outer cap | `SATISFIABLE`, exit 10 in 0.129 exploratory wall seconds; reconstructed all 2,809 gate variables and checked original XCNF/group relation |
| N83 pinned | same | 20-second outer cap | `WALL_CAP`, no terminal SAT/UNSAT conclusion |

The plain inputs were decompressed from the archived
`formulas/n53_pinned.anf.gz` and `formulas/n83_pinned.anf.gz` files. The
pre-protocol N83 timeout is censored and separate from its frozen
90-second panel row.
