# Column-disjoint W18 pair codes and an exact eight-pair source gate

The fixed-seed W18 source has a **33,127-code folded-column-disjoint subset**
out of 33,191 admissible pair codes. Restricting every one of the eight
Frobenius slots to this subset and requiring different codes across slots
guarantees sixteen distinct folded factor-base columns *inside* the SAT
formula. The gate retains the archived constructed witness. It is a reusable
source-aware constraint for the existing N131 eight-pair target formula,
without changing its field arithmetic or public target.

The source is the audited W18 mask-to-column table on
`EC1N131Ckb1heb5f1998f20b`, with seed-XOR mask `212`, rotations
`0,16,...,112`, subgroup order
`680564733841876926932320129493409985129`, and 33,191 allowed
unordered source pairs per slot. Build a graph whose vertices are folded
columns and whose edges are the allowed pair codes. Its components are
33,082 isolated edges, 26 components with two adjacent edges, 18
three-edge paths, and one three-edge star. Greedy selection in increasing
code order removes 64 edges, leaving 33,127 edges with disjoint endpoints.
The eight archived constructed codes are all retained and distinct.

The independent [audit](audit_result.json) reconstructs the graph and the
degree-eight coefficient of its matching polynomial:

```text
M(x) = (1+x)^33082 (1+2x)^26 (1+3x+x²)^18 (1+3x).
8! [x^8] M(x) = 1,471,617,230,621,064,265,396,063,736,810,928,000.
```

Each selected source pair has four signed leaf choices. Thus the exact mean
number of ordered, sixteen-distinct-column source tuples mapping to a
**uniformly sampled subgroup point** is
`8! [x^8] M(x) · 4^8 / r = 141.711584556466...`. The restricted
33,127-edge matching gives a certified lower mean of
`(33127)_8 · 4^8 / r = 139.540490209019...`, versus the unrestricted
pair-code ceiling `33191^8 · 4^8 / r = 141.831660832996...` before
column exclusions. These are exact averages over the subgroup, not a
coverage probability or a relation-yield measurement for the frozen public
point. They show that the matching restriction keeps at least 98.47% of
the exact average tuple count while removing all cross-slot column repeats.

The [reusable gate](matching.py) emits the positive-polarity source BDD for
the matched code subset in every slot, then 28 pairwise 17-bit code
disequalities. The [compile control](compile_result.json) checked the BDD
against all `2^17` codes and compiled eight slots with the repository XCNF
backend. It measured the gate alone:

| Eight-slot source gate | Variables | CNF clauses | Native XOR rows |
| --- | ---: | ---: | ---: |
| Prior source BDD | 104,833 | 209,153 | 0 |
| Matched BDD plus code distinctness | 105,181 | 208,925 | 476 |

The [frozen count protocol](protocol.json), [result](result.json),
[audit protocol](audit_protocol.json), and [compile protocol](compile_protocol.json)
bind source and input hashes. A first local run stopped before writing a
result because the host Python lacked `int.bit_count`; its
[failure receipt](failure_v1.json) and original [protocol](protocol_v1.json)
are retained. The revised count and independent audit completed. These are
deterministic combinatorial and formula-construction checks; no CPU timing
ratio is being promoted.

## Full-formula search control

The [overlay builder](overlay.py) appended the matching restriction to the
existing four-preimage, known-satisfiable **witness-unpinned** constructed
formula. It kept the original arithmetic and target rows byte-for-byte,
then added 512 forbidden-code clauses, 28 code-disequality clauses, and 476
native XOR rows. The resulting [XCNF](matched_unpinned_constructed.xcnf)
has 309,708 variables and 596,869 total rows. The independent
[overlay audit](overlay_audit_result.json) checked all 595,853 baseline rows
for byte identity and extended the archived witness to satisfy every added
row. The [build receipt](overlay_result.json) and its
[protocol](overlay_protocol.json) bind both XCNF files and source hashes.

| Frozen witness-unpinned control | Baseline four-preimage source | Matching overlay |
| --- | ---: | ---: |
| Solver / parent caps | 120 s / 135 s | 120 s / 135 s |
| Status | `PARENT_TIMEOUT` | `PARENT_TIMEOUT` |
| Parent wall | 135.086 s | 135.218 s |
| Peak child RSS | 377,339,904 B | 153,698,304 B |
| Audited unpinned model | 0 | 0 |

The [matching run receipt](solver_result.json), [frozen solver
protocol](solver_protocol.json), and [stdout](solver.stdout.txt) retain its
status and cap. These runs were not paired on an isolated host, so their
memory and wall observations are diagnostics rather than a controlled
performance ratio. Both formulas are satisfiable by the independently
checked constructed witness; the bounded searches neither found a model
nor proved unsatisfiability. The matching gate gives a cheap exact
distinct-column representation, but this control provides no evidence that
it clears the N131 search bottleneck. The ordinary public-point run was
therefore not launched for this variant.

The next algorithm gate is an implicit, target-conditioned join that rejects
families while at least two pair outputs remain free. First recover an
unpinned ordinary row on the frozen N41 same-rotation public point within
120 seconds and 4 GiB, with independent checked-Sage replay. Then provide
a source-bound N131 operation and memory projection for the complete search
within 600 seconds and 4 GiB before querying the frozen N131 point. Count
failed probes and rank-increasing verified rows; keep the one-target online
DLP and matched rho comparison as the final pipeline measurement. Candidate
and run IDs remain null until the complete method and workload are specified.
