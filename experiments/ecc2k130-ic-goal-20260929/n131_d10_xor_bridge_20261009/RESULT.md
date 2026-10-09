# Exact CNF bridges for the N131 d10/m15 point-decomposition query

Moving the 4,040 ternary XOR equations that touch intermediate
point-coordinate variables into equivalent CNF partitions the first frozen
N131 d10/m15 precomputation query's native-XOR graph. Its largest component
falls from 168,622 rows to **9,894 rows and 14,421 columns**, within the
unchanged CryptoMiniSat limits of 10,000 rows and 15,000 columns per Gaussian
matrix. The full Boolean formula remains equivalent for every assignment;
the target point, 139,384 usable factor-base points, 532 folded columns,
15-summand circuit, and solver seed remain the same.

The formula builder allocates 15 × 10 leaf-selector variables first, then
13 × 131 intermediate point-coordinate variables numbered 151 through 1853.
Exactly 4,040 native-XOR rows contain one of those intermediate variables,
and every such row has three literals. Each odd-parity ternary XOR is replaced
by the four CNF clauses excluding its four even-parity assignments. No
variable is introduced or fixed.

| Frozen first d10/m15 precomputation XCNF | Original | CNF bridges |
| --- | ---: | ---: |
| Variables | 282,598 | 282,598 |
| CNF clauses | 225,092 | 241,252 |
| Native XOR rows | 208,783 | 204,743 |
| Largest XOR component, rows | 168,622 | 9,894 |
| Largest XOR component, columns | 225,304 | 14,421 |
| XCNF bytes | 10,887,544 | 11,118,156 |

The [transform receipt](bridge_cnf/result.json) binds the source XCNF hash,
transformed input, source code, exact variable interval, and record counts.
The [independent audit](bridge_cnf/independent_audit.json) compared every
unchanged original record byte-for-byte, enumerated the four forbidden
variable assignments for each converted row independently of the transform,
matched its four new clauses, and counted all transformed XOR components.
The transformed XCNF has 445,995 records and 143 XOR components. This audit
establishes formula equivalence and input component geometry. Solver
preprocessing may change the matrix partition or resource use.

The [separate one-query protocol](protocol.json) uses the same first
precomputation point and solver seed as the frozen d10 R1 run, one worker,
a 580-second solver-stage wall cap, and a 4-GiB combined-RSS cap. It keeps
`candidate_id` and `run_id` null until a complete IC pipeline is specified.
The solver-stage interval excludes original formula construction and this
conversion; both costs must be included in any complete relation-query or
single-target online accounting. Any SAT model needs independent checks
against both saved XCNFs and an installed-Sage point, subgroup, factor-base,
and folded-row replay before it counts as a relation. The original d10
candidate and the queued public-Q d13/m12 probe retain their frozen run
order; this proposal has its own run record.

The frozen [bridge attempt](ordinary_precompute_R1/result.json) ended
`CENSORED_TIME` at its 580-second parent wall cap with zero solver status or
model lines. Its sampled peak combined RSS was 1,495,334,912 bytes. The raw
CryptoMiniSat log selected ten 9,543×13,720 Gaussian matrices at
initialization, confirming that the exact CNF bridges cleared the original
matrix-size rejection under unchanged solver limits. The
[independent terminal audit](ordinary_precompute_R1/independent_terminal_audit.json)
checked the frozen command, raw log hashes, drained solver, and censored
classification. This is one contended-host solver-stage result; it does not
establish a useful-relation rate or a CPU timing advantage. The
[bridge-plus-projection follow-up](../n131_d10_bridge_projection_20261009/RESULT.md)
has separately passed exactness and component audits and is measured under
its own frozen 580-second/4-GiB envelope.
