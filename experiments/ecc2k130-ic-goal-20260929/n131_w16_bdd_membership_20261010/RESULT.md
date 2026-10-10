# Exact compact W16 source membership for the N131 five-pair circuit

The W16 source-membership constraint is now represented by a reduced binary
decision graph. It accepts exactly the same **32,796 rational W16 masks** as
the archived circuit, while replacing ten copies of 32,740 long forbidden-mask
clauses with short branch implications. The complete five-pair XCNF remains
satisfiable by the frozen twelve-point constructed witness. Relative to the
byte-identical prior W16 formula, this encoding removes **162,130 CNF clauses
(30.68%)** and **16,116,145 bytes (47.37%)**. It adds 83,000 auxiliary
variables; the 34,600 native-XOR rows and all source, target, column, and
group equations remain the same.

## Exact construction and audit

The [graph builder](bdd.py) reduces the 16-bit membership truth table from
the archived [W16 source](../n131_w16_w18_sixpair_width_gate_20261010/support_w16.tsv)
to **8,300 nodes**. At a node for mask bit `i`, a true node variable implies
the child selected by bit `i`; a true root therefore forces the selected
terminal to be true. The other branches may remain false. Conversely, each
accepted mask extends to an assignment of all auxiliary variables by setting
the nodes on its selected path. This proves that the emitted forward clauses
are equivalent to source membership after existentially quantifying the
auxiliary variables.

The [exhaustive audit](audit.json) evaluates all **65,536** masks against the
decision graph and independently compares the accepted set with the archived
support file: 32,796 accepted and 32,740 rejected. The separate
[small-width exhaustive test](test_bdd.py) checks the emitted CNF under every
auxiliary assignment for all 254 nonconstant three-bit membership sets.
The [constructed-control
receipt](control.json) verifies every clause and XOR row under a completed
assignment, with the same source masks, target branch, middle coordinates, and
prior independently verified group lift. Its source and runtime are fixed in
the [protocol](protocol.json), and the local Sage invocation used the checked
repository launcher with a saved [runtime receipt](sage_runtime_info.json).

| Frozen constructed residual | Prior forbidden-mask XCNF | Decision-graph XCNF |
| --- | ---: | ---: |
| Variables | 98,640 | 181,640 |
| CNF clauses | 528,425 | 366,295 |
| Native-XOR rows | 34,600 | 34,600 |
| XCNF bytes | 34,024,982 | 17,908,837 |
| Source-membership clauses | 327,400 | 165,270 |

The [bounded public-only query](query.json) rebuilt the compact formula and
matched its control SHA-256. CryptoMiniSat ran with one worker, a 120-second
total cap, and a 4-GiB combined RSS cap. It returned `CENSORED_TIME` at
115.089 seconds total wall (17.745 seconds formula build, 97.344 seconds
solver interval), with 247,627,776 bytes sampled peak combined RSS. The raw
log contains **200 restart lines**, establishing that search began, and no
model or final solver status. Sampled solver CPU was only **7.171 seconds**
during that search wall interval on this contended host. The
[terminal audit](query_audit.json) binds the control formula, source hashes,
raw solver output, cap, and no-model status. This row does not measure a
search advantage or natural relation yield.

## Next algorithmic gate

The compact encoding improves formula transfer and leaves a materially
smaller SAT input, but the 83,000 new auxiliaries can alter propagation in
either direction. The next controlled comparison should run the frozen old
and new formulas on the **same constructed residual**, same solver binary and
flags, paired order, and an isolated CPU receipt, measuring complete
target-dependent construction, solver CPU and wall, conflicts, memory, and
verified group output. A reduction in file size alone is not an IC speedup.

The decisive method gate remains a **public-only unpinned relation** that fits
the N131 one-worker 600-second/4-GiB envelope. Before more wide-field search,
test a target-conditioned partial-output generator on the existing N41 W6
public control, requiring an independently replayed relation while counting
all proposed outputs, inverse calls, failed branches, and wall/RSS. Transfer
only a generator with a credible N131 operation bound; then measure ordinary
relation yield, rank novelty, final factor logs, and one-target online scalar
recovery against same-point rho. This experiment keeps `candidate_id: null`
until that complete pipeline is specified.
