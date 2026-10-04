# Q1419: partial-pinning diagnosis for four-summand balanced S3

This frozen stage experiment asks which free-variable family makes the known
satisfiable balanced-S3 SAT search stall. It reuses the exact archived N53
Q1410 ordinary target and N83 Q1408 planted control. The N53 target has a
separately known four-point representation, but the solver is given only the
specified pins. The N83 target was constructed from a known representation.
These are **validation controls**, not ordinary-yield samples.

The [protocol](protocol.json) freezes all 16 cells, their order, the exact
curve and factor-base records, input artifacts and hashes, the CryptoMiniSat
binary, the checked Sage runtime, and the 60-second/one-million-conflict cap.
Each cell is a separate process, with one SAT thread. The controls release
pair intermediates, the target-preimage selector, and leaf coordinates in a
fixed sequence. `two_split` and `two_same` distinguish freeing one leaf in
each pair from freeing both leaves in one pair.

| Degree | Exact curve ID | Base policy | Actual B | Folded K | Input law |
| --- | --- | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | Q1301 W≤3 | 24,062 | 227 | archived ordinary target, known satisfiable |
| 83 | `EC1N83Ckb1h876c2921cb64` | Q1325 W≤5 | 30,977,592 | 186,612 | archived planted, known satisfiable |

Run through the repository's checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1419_partial_pin/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py --degree 53 --cell full_lock --preflight
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1419_partial_pin/run_cell.py --degree 53 --cell full_lock
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1419_partial_pin/verify_archive.py
```

The runner saves the complete compressed XCNF, solver stdout/stderr, and one
receipt per cell, including failures and censored runs. The verifier parses
the serialized XCNF independently of the writer, checks any SAT assignment
against every CNF and XOR row, then replays accepted leaves with the curve
group law and exact factor-base membership. It shares the archive's field
and curve implementation with the runner; a separate Sage replay is needed
before promoting any newly found relation as independently checked.

All wall times here are exploratory because the host has no isolation
receipt. The `PS1` stage IDs include actual `fb<B>` counts; `candidate_id`
stays null because collection, final matrix solving, descent, and target
recovery are absent. No cell measures natural relation yield or a complete
`2^x` solve. The decision gate is diagnostic: which released pins first make
known satisfiable search hit the cap, and whether N53 and N83 agree. A new
search method must then recover an unpinned ordinary N53 relation and an
ordinary N83 relation on Q1325 before fitting any N131 solver growth.

## Frozen results

The [archive verifier](verification.json) checked all 16 receipts, exact
formula archives and solver logs. Every SAT assignment satisfies the
serialized CNF and XOR rows and replays to a four-distinct-column relation
in the exact base. The three SAT cells all use the already archived witness
leaf coordinates, which have independent checked-Sage replays in the parent
Q1410 and Q1408 records. The times below are solver-only, exploratory
seconds; `cap` is the one-million-conflict stop, and `wall` is the external
60-second stop.

| Pinning cell | N53 result / seconds | N83 result / seconds |
| --- | --- | --- |
| `full_lock` | verified SAT / 0.029 | verified SAT / 0.084 |
| `free_mids` | cap / 15.382 | cap / 19.653 |
| `free_target` | verified SAT / 3.528 | cap / 55.361 |
| `three_leaves` | cap / 15.887 | cap / 23.293 |
| `two_split` | cap / 55.739 | wall / 60.005 |
| `two_same` | cap / 13.751 | cap / 26.397 |
| `one_leaf` | cap / 55.097 | wall / 60.007 |
| `target_only` | cap / 42.028 | wall / 60.005 |

Releasing the two pair-intermediate x coordinates alone stalls this SAT
encoding at both degrees even while all four leaf x coordinates remain
fixed. Freeing the target selector makes the N53 case easy again, showing
that the search behavior is not monotone in the number of free variables.
The N83 free-target case stays censored. These controls identify a useful
engineering target, but do not show that pair intermediates dominate the
cost of an unpinned ordinary query. No ordinary N83 relation was found.

## Next solver gate

Eliminate each pair-intermediate SAT search by solving the fixed-pair
`S3(x1,x2,z)=0` quadratic in the field and branching explicitly over its
roots. The first correctness gate is the same frozen known-satisfiable
N53/N83 controls with all pair intermediates free. Then require an unpinned
ordinary N53 relation, followed by at least one ordinary N83 four-point
relation on exact Q1325 W≤5. Preserve every failed query and operation count,
independently replay the N83 relation, and measure useful-row and novel-rank
rates on fresh ordinary targets. Pair the N53/N83 costs with the existing
pair-table stages on the same curves, targets and base policies. A degree-131
`2^x` fit remains unknown until those rates and all setup, matrix, descent,
and replay costs are present in one calibrated unit.
