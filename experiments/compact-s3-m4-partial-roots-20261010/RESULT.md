# Exact first-pair S3 roots with free remaining leaves

Q20261010171000 inserts the exact two-root disjunction for the first pair
midpoint into four archived balanced four-summand XCNFs. The first pair's
two leaf x coordinates are fixed; the remaining one or two leaves are free.
The construction adds one selector and `2n` binary clauses while retaining
every original clause and XOR row. The independent archive audit passes on
all four formulas and eight solver receipts.

| Curve | Pinned leaves | Solver | Status at 60 s cap | Child CPU s | Peak child RSS MB |
| --- | ---: | --- | --- | ---: | ---: |
| `EC1N53Ckb1hf77aab617904` | 3 | default | `BOUNDED_UNKNOWN` | 22.46 | 127.7 |
| `EC1N53Ckb1hf77aab617904` | 3 | Gaussian | `BOUNDED_UNKNOWN` | 28.37 | 183.6 |
| `EC1N53Ckb1hf77aab617904` | 2, same pair | default | `BOUNDED_UNKNOWN` | 48.13 | 139.1 |
| `EC1N53Ckb1hf77aab617904` | 2, same pair | Gaussian | `BOUNDED_UNKNOWN` | 23.98 | 92.4 |
| `EC1N83Ckb1h876c2921cb64` | 3 | default | `BOUNDED_UNKNOWN` | 10.87 | 68.7 |
| `EC1N83Ckb1h876c2921cb64` | 3 | Gaussian | `BOUNDED_UNKNOWN` | 3.91 | 31.5 |
| `EC1N83Ckb1h876c2921cb64` | 2, same pair | default | `BOUNDED_UNKNOWN` | 3.66 | 39.5 |
| `EC1N83Ckb1h876c2921cb64` | 2, same pair | Gaussian | `BOUNDED_UNKNOWN` | 5.35 | 39.5 |

Every run exited by the external wall cap with code -9. The archived solver
streams show active search; none finished a model or an UNSAT proof. These
are known-satisfiable partial-search controls, so the rows measure neither
ordinary relation yield nor a completed decomposition cost. The wide CPU
share variation within the same wall cap shows host contention. Timing
ratios are exploratory and do not establish a solver speedup.

The exact base records are N53 `B=24062`, `K=227`, W<=3 and N83
`B=30977592`, `K=186612`, W<=5. The proposal retains `candidate_id: null`,
`run_id: null`, and `isogeny: "none"` (`ISO0`). The freeze SHA-256 is
`9ba564215140fc1c2968fac9f9bb98f674ae786bd075d7054741a63b8dee7f6c`.
The saved `audit.json` records the PASS result. To replay, move that output
aside and run `python3 audit.py` from the repository checkout; the auditor
checks the formula, root, curve, model, solver, and source hashes.

The next solver experiment should branch explicitly on the two exact first-
pair roots and remove that pair's S3 arithmetic gate from the formula. It
can then measure whether root conditioning reduces the N53/N83 free-leaf
search, on the same archived target and base, before any degree-131
extrapolation. A complete degree-131 work exponent still needs ordinary
query yield, novel rank per query, charged collection, final matrix solving,
target descent, and correctness replay.
