# CNF bridges followed by exact XOR projection on the N131 d10 query

Applying fill-limited XOR elimination after the exact intermediate-coordinate
CNF bridges reduces the frozen d10/m15 precomputation query to **139,159
variables and 61,304 native-XOR rows**. Its largest native-XOR component
has **2,645 rows**; the widest component has **5,271 columns**. All 241,252
CNF clauses remain, including the 16,160 clauses that exactly replace 4,040
ternary XOR bridges. The one-times XOR-literal budget preserves the bridge
formula's 887,439 XOR literal occurrences.

| Same frozen precomputation point | Original | CNF bridges | Bridges + projection |
| --- | ---: | ---: | ---: |
| Variables | 282,598 | 282,598 | 139,159 |
| CNF clauses | 225,092 | 241,252 | 241,252 |
| Native XOR rows | 208,783 | 204,743 | 61,304 |
| Largest XOR component, rows | 168,622 | 9,894 | 2,645 |
| Widest XOR component, columns | 225,304 | 14,421 | 5,271 |
| XCNF bytes | 10,887,544 | 11,118,156 | 10,156,866 |

The [projection receipt](budget1/result.json) binds the exact bridge input,
projected XCNF, 143,439 eliminated variables, reverse-lift rows, source
hashes, and checked-Sage runtime. The
[independent pivot audit](budget1/independent_elimination_audit.json)
replayed all 143,439 pivots and 208,297 row additions, then matched every
mapped CNF clause and residual XOR record. The
[component audit](independent_component_geometry.json) recomputed both
native-XOR graphs and checked the frozen 10,000-row/15,000-column Gaussian
limits. The [preceding bridge audit](../n131_d10_xor_bridge_20261009/bridge_cnf/independent_audit.json)
checks the exact CNF replacement of each removed ternary XOR row. Together
these receipts establish Boolean equivalence to the saved unmodified d10
query and the stated component geometry; they do not measure natural
relation yield.

The [separate one-query protocol](protocol.json) retains the original
precomputation point and solver seed, one worker, a 580-second solver-stage
cap, and a 4-GiB combined-RSS cap. `candidate_id` and `run_id` remain null
because this is a method screen, not a complete IC pipeline. Its solver-stage
clock excludes original formula construction and both exact transforms.
Any model must pass the projected XCNF, reverse lift, bridge and original
XCNFs, then independent installed-Sage point, subgroup, factor-base, and
folded-row replay. This run is scheduled after the active bridge-only trial
drains, with each timeout or failure retained separately. The original d10
candidate and queued d13/m12 public-Q probe keep their frozen sequence.
