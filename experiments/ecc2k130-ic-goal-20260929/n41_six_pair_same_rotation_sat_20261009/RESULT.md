# Six-pair same-rotation N41 SAT gate

**The exact twelve-leaf transformed-S3 formula passed a full known-row
assignment and independent Sage group replay.** Its seed-mask and target-lift
pinned CryptoMiniSat control then reached the frozen 30-second wall cap without
a model. The public-only N41 query was not started under the protocol gate.
This candidate has not earned an N131 run.

The frozen control uses the degree-41 Koblitz `b=1` curve
`EC1N41Ckb1h7d5e80d3c4d0`, six same-rotation W6 pairs at Frobenius
rotations `[0,7,14,21,28,35]`, twelve rational source points, and twelve
distinct signed-Frobenius columns. The separate public point is the frozen
`n41_adjacent_pairpair/public_target.json` target. A deterministic planted
point is used only to check the formula. The [protocol](protocol.json) binds
the source, geometry, points, checked Sage runtime, one-worker solver,
30-second pinned cap, 120-second public cap, 4-GiB process-tree cap, and
conflict limits. Complete-pipeline candidate and run IDs remain null.

Six pair links use the exact same-rotation rank-11 product and transformed
S3 equation. Three pair-pair links, one four-pair link, and one target link
form the target-coupled tree. The [source](circuit.py) preserves every
nonexceptional branch; [run.py](run.py) constrains rational seed masks and
distinct folded columns. Its pinned [XCNF](preflight/system.xcnf) has 25,204
variables, 14,256 AND gates, 10,462 native XOR rows, 46,766 CNF clauses,
and 1,140,298 bytes. The [preflight](preflight/receipt.json) completed an
assignment of every wire and checked every clause and XOR row.

| Gate | Status | Target-dependent wall | Process-tree peak RSS |
| --- | --- | ---: | ---: |
| Pinned twelve-point control | `PARENT_WALL_CAP`, no model | 30.033763416 s | 284,049,408 B |
| Public-only N41 target | `NOT_STARTED_CONTROL_TIMEOUT` | unknown | unknown |

The [pinned receipt](control/receipt.json) retains the formula digest,
solver command, resource sample, and exclusive phase accounting. The
[independent checked-Sage audit](audit.json) replayed all twelve raw points,
their cofactor-four projections, distinct signed-Frobenius orbits, each pair
and middle sum, the final target, subgroup membership, and the timeout
accounting. The timeout is a censored search outcome: it does not certify
unsatisfiability.

This control isolates the next implementation decision. A generic native-XOR
SAT tree still spends its bounded control interval on full-field internal
outputs after seed masks are fixed. The next solver should obtain those
outputs by exact pair inversion or group arithmetic and use its search budget
on target-conditioned seed or pair-output generation. A new public-only
N41 gate must be frozen and replayed before projecting this six-pair policy
to N131. No CPU timing ratio from this unisolated host is promoted as a
speedup.
