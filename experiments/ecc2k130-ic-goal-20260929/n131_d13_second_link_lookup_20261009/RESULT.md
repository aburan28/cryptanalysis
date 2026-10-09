# Exact second-link lookup for the N131 d13 public-target chain

For each of the two frozen first-link roots and all 4,134 valid third-leaf
codes, exact curve arithmetic gives **two distinct finite second-link
outputs**. The [independent full-table audit](audit.json) replays every
entry by curve addition, the expanded S3 equation, and the quadratic
root-sum identity. Its nonzero leading-coefficient checks certify that the
two values are the complete S3 root set for each code. Each branch has 8,268
distinct output masks across its 4,134 codes, so an output mask identifies
one code and one root choice within that branch.

| First-link branch | Valid third-leaf codes | Checked finite outputs | Distinct output masks | Lookup XCNF variables | Lookup XCNF records | Added clauses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 4,134 | 8,268 | 8,268 | 119,424 | 1,163,179 | 870,467 |
| 1 | 4,134 | 8,268 | 8,268 | 119,424 | 1,162,645 | 869,933 |

The [frozen protocol](protocol.json) retains the exact d13 basis, original
public-Q XCNF, prior two-root receipt, checked-Sage runtime, and source
hashes. The 1.1-MB [table](table.json) stores `[code, root0, root1]` for
each branch; the root names denote sorted field masks, not a planted sign.
There were no exceptional or degree-drop cases among the checked codes.

The [encoder](encode.py) adds one selector variable per valid code and one
root-choice bit to each previously audited first-link branch. A selector is
equivalent to the 13-bit third-leaf code. It forces each of the 131 next
partial-coordinate bits to the selected root value. When a code is fixed,
43–87 output bits are already common to both roots and become unit
consequences; the remaining bits depend on the root-choice bit. This is a
precise propagation property of the encoding, not a measured solver gain.
The [independent encoding audit](encoding_audit.json) byte-compares every
prior XCNF record, every appended clause, both formula hashes, and the
local Boolean output rule. The resulting formulas are about 27.3 MB each.

This is a frozen **proposal**, with `candidate_id: null` and no new target
query row. The next gate is an ordinary smaller-field public-target control:
pair an exact second-link lookup with the same chain representation, verify
any solver model by independent point addition, and compare complete query
cost and useful relation yield with the source circuit on frozen inputs.
Only after that gate should the N131 lookup be run under the one-worker,
600-second/4-GiB envelope. N131 models then require original-XCNF and
independent checked-Sage relation replay. The full single-target online
interval and same-point rho comparison remain separate downstream gates.
