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
