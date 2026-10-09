# Exact bridge and bounded XOR projection for the N131 d13 public target

The frozen d13/m12 public-Q point-decomposition formula now has an exact
CNF-bridge representation whose native-XOR components fit CryptoMiniSat's
10,000-row and 15,000-column Gaussian limits. Fill-limited elimination
reduces it to **115,289 variables and 51,122 native-XOR rows** while keeping
the largest component at **3,038 rows** and the widest at **5,003 columns**.
This is a solver-input method proposal on the one supplied challenge-curve
public point; `candidate_id` and `run_id` remain null.

| Same N131 d13/m12 public-Q formula | Original | Exact CNF bridge | Bridge plus projection |
| --- | ---: | ---: | ---: |
| Variables | 232,244 | 232,244 | 115,289 |
| CNF clauses | 228,629 | 241,433 | 241,433 |
| Native XOR rows | 171,278 | 168,077 | 51,122 |
| Largest native-XOR component, rows | 133,891 | 9,674 | 3,038 |
| Widest native-XOR component, columns | 177,655 | 13,982 | 5,003 |
| XCNF bytes | 11,202,092 | 11,382,569 | 10,529,623 |

The [bridge audit](bridge_cnf/independent_audit.json) compares every original
record to the transformed formula and independently enumerates the truth
table of each of the 3,201 replaced ternary XOR rows. All other clauses and
XOR rows match byte-for-byte. The
[projection audit](budget1/independent_elimination_audit.json) replays all
116,955 private-variable pivots and 169,121 row additions, then matches every
mapped CNF clause and residual XOR record. The projected formula retains
738,741 XOR-literal occurrences under its one-times input-literal budget;
there are no free private variables or projected contradictions. The
[component audit](component_audit.json) recomputes the bridge and projected
XOR graphs from their saved XCNFs. These checks establish exact Boolean
equivalence to the public-Q source formula and the stated initial component
geometry.

The separate [solver protocol](solver_protocol.json) freezes the transformed
formula, source and audit hashes, one public Q, seed `2026100613`, one
CryptoMiniSat worker, a 580-second solver-stage wall cap, and a 4-GiB
combined-RSS cap. It uses `--xor=0` because the matched d10 bridge control
showed that default XOR discovery reconstructed a large XOR component from
CNF during simplification. The [checked runner](run_public.py) is prepared;
its first unpinned attempt is queued after that d10 control drains. Any model
must pass projected and reverse-lifted original-XCNF checks, exact curve
point decoding, factor-base membership, and independent checked-Sage group
replay before it counts as a relation.

The saved solver-stage interval excludes formula construction and both
target-dependent exact transformations. Their costs must be included in a
complete single-target online measurement. Initial matrix fit is a useful
solver-input property; ordinary relation yield, rank, factor logs, target
scalar, and paired rho timing remain to be measured.
