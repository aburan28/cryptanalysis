# Q1417: bounded five-summand compact-S3 PDP gate

This is a **point-decomposition stage experiment**, not a complete IC
candidate or ECDLP solve. It asks whether a four-link, five-summand S3
formula with all raw cofactor preimages can produce a verified relation on
two exact compact-orbit bases. The protocol, producer source, binary, bases,
targets, and checked Sage runtime were frozen before the measured searches.
The first frozen protocol failed before solver launch because macOS rejected
its `RLIMIT_AS`/`RLIMIT_DATA` setting. That failure, its original protocol,
and its formula archive remain in Git. Revision 2 replaced that guard with
sampled child RSS and was committed before the six searches below.

| Field and exact base | Search | Solver outcome | Verified relations | Exploratory target-dependent PDP interval |
| --- | --- | --- | ---: | ---: |
| N53, W≤3, B=24,062, K=227 | planted, all leaf/intermediate/preimage variables pinned | SAT | 1 | 0.291 s |
| N53, same base | same planted target, no pins | external 60 s timeout | 0 | 60.007 s |
| N53, same base | archived ordinary public target `74f2979b3e68` | 1,000,002 conflicts; `INDETERMINATE` | 0 | 58.557 s |
| N83, W≤4, B=1,934,066, K=11,651 | planted, all leaf/intermediate/preimage variables pinned | SAT | 1 | 0.227 s |
| N83, same base | same planted target, no pins | external 60 s timeout | 0 | 60.013 s |
| N83, same base | archived ordinary public target `bab50a1e5f66` | 1,000,002 conflicts; `INDETERMINATE` | 0 | 90.214 s |

The producer's historical `solver_failure` label for the two ordinary rows
is the CryptoMiniSat exit code 15 at the frozen one-million-conflict stop.
The raw logs explicitly say `s INDETERMINATE`; this is a censored search,
not a proof of unsatisfiability or a crashed solver. The unpinned planted
rows were externally stopped at their frozen 60-second wall cap. Ordinary
rows had a 120-second external cap, but both reached the conflict cap first.
One ordinary query per field is an observed diagnostic, **not** a natural
relation-yield estimate. The planted rows are correctness controls and do
not estimate ordinary-target coverage.

The formula selects a complete raw target preimage coset: 428 preimages for
N53 and four for N83. Leaves obey the exact normal-basis weight bound, and
every accepted model must replay five signed curve points through cofactor
projection into the archived exact factor base. The independently verified
locked models satisfy every archived CNF and XOR row and sum to their public
targets in the declared subgroup. The unpinned N53 formula has 35,823
variables, 125,703 CNF clauses, and 1,060 XOR rows; N83 has 86,386,
252,012, and 1,660 respectively. Locked controls have additional unit
clauses, preserved in their archive shapes.

`runs/independent_replay.json` binds the six receipts to the exact formula
and solver-log hashes. `verify_archive.py` independently evaluates the SAT
models against the archived formulas and checks the curve group law, subgroup
order, target preimage, signed lifts, base membership, and target sum. It
does not call the producer's formula builder or model replay routine.

To replay locally, use the repository's checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/m5-s3-gate-20261004/verify_archive.py
```

The verifier refuses to overwrite its committed replay receipt; move that
receipt aside in a disposable checkout before rerunning, and compare the
new receipt's rows and hashes. This run is on an unisolated CPU host. Its
times establish neither a controlled CPU speedup nor an online IC result:
there is no relation matrix, factor-base logarithm computation, target
descent, or recovered discrete logarithm. `candidate_id` and `run_id` remain
null under the repository's candidate-measurement contract.

## Decision and next gate

Plain CryptoMiniSat search on this five-summand chain passes the locked
correctness gate but fails to find even the *known* planted relation when
its variables are released under 60 seconds. That makes unmodified m5 SAT
a poor immediate basis for a full-rank collector, despite favorable
combinatorial coverage estimates elsewhere. This is a solver and encoding
result, not evidence that five-summand relations are rare or that SAT cannot
work after structural changes.

The next controlled experiment should retain these exact N53/N83 bases,
public targets, complete cofactor cosets, source-bound receipts, and caps,
then introduce a **proved permutation symmetry break** on five leaves.
First establish equivalence on all permutations of archived planted
relations, including exceptional intermediate sums. Then run the same
unpinned planted controls; promote the method to additional held-out
ordinary targets only if it verifies a relation without planted pins.
Record conflicts, elapsed PDP time, memory, zero-yield cells, and group-law
replay for each target. If the unpinned control still fails, the next
investigation should measure a staged hybrid or algebraic decomposition on
this same workload before attempting N131 transfer. Do not infer N131
feasibility from these smaller-field stage timings.
