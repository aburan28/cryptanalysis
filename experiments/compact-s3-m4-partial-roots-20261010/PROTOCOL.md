# Q20261010171000: one fixed-pair S3 root implications

Measure how exact S3 midpoint implications help while other leaves remain
free. Reuse Q1419's exact `three_leaves` and `two_same` balanced four-sum
XCNFs at N53 and N83. In both cells, leaves 0 and 1 are pinned to the
archived witness; compute their two S3 roots and constrain pair midpoint 0
to either root. Preserve every original CNF/XOR row and all unpinned leaf
variables. This adds one selector and `2n` binary clauses. Run default
CryptoMiniSat and an active-Gaussian variant on each augmented formula.
N53 uses a 10,000-column Gaussian limit; N83 uses 25,000 columns because
the frozen N83 matrix has 20,916 columns.

Use the Q1419 curve, target, actual factor-base point count, folded columns,
enumerated-set digest, and archived formula bytes without modification.
N53 is `EC1N53Ckb1hf77aab617904`, Q1301 W<=3, `B=24062`, `K=227`.
N83 is `EC1N83Ckb1h876c2921cb64`, Q1325 W<=5, `B=30977592`,
`K=186612`. Proposal `Q20261010171000` has `candidate_id: null`,
`run_id: null`, and `isogeny: "none"` (`ISO0`).

Freeze source, solver, parent receipts, formula hashes, exact root sets,
settings, and eight-cell order before running. Use one solver thread, seed
zero, one million conflict cap, and 60-second external wall cap per cell.
Record construction time, one-pair oracle calls, solver status, conflicts,
child RSS, wall time, stdout/stderr, and group-law replay for any SAT model.
Capped runs remain `BOUNDED_UNKNOWN`; host wall times are exploratory.
These known-satisfiable controls test partially free search, not natural
ordinary-query relation yield.
