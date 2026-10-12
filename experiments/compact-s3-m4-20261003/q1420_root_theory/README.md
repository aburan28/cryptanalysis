# Q1420: external S3 root clauses in a four-summand search

Q1420 tests a compact four-summand point-decomposition stage on the exact
Q1301 N53 W≤3 and Q1325 N83 W≤5 bases. It is stacked on Q1419's frozen
inputs and controls. The [protocol](protocol.json) fixes the exact EC1
curves, actual base counts and digests, one ordinary public point per degree,
known-satisfiable controls, implementation and binary hashes, run order, and
60-second/one-million-conflict limits. `candidate_id` remains null because
this is one PDP stage rather than a complete IC method; `isogeny` is `none`.

The Boolean formula contains four bounded-weight leaf x coordinates, two
pair-intermediate x coordinates, the target-preimage selector, and only the
final balanced-tree S3 link. The first two S3 links are omitted. CaDiCaL's
external-clause callback watches each leaf pair. Once a pair is fully
assigned, it computes all zero, one, or two exact roots of `S3(a,b,z)=0`
in the archived polynomial field representation and adds guarded clauses
that restrict the corresponding intermediate to those roots. The guard is
the full leaf assignment, except that a leaf at the maximum Hamming weight
is fixed by its positive support under the existing at-most-weight CNF.
The first differing intermediate bit selects between two roots. Every
external clause is implied by the omitted S3 link and retains the original
problem's solutions. The callback memoizes observed pair assignments.

This differs from Q1319's Boolean half-trace/inverse root circuit and from
Q1327/Q1328's target-independent pair-sum index. It does not build a K²n
table. The root callback may still see too many pair assignments, and
XOR-to-CNF conversion may weaken propagation. These are measured failure
modes, not assumed away.

## Frozen gates and names

| Degree | Curve ID | Base | Actual B | Folded K | Cases |
| --- | --- | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | Q1301 W≤3 | 24,062 | 227 | full lock, free mids, ordinary |
| 83 | `EC1N83Ckb1h876c2921cb64` | Q1325 W≤5 | 30,977,592 | 186,612 | full lock, free mids, ordinary |

The controls inherit Q1419's known leaves. The ordinary cases use the
archived Q1410 N53 and Q1408 N83 ordinary public targets with no witness
pins. `PS1...PDP4theory...` identifies each exact stage configuration;
the workload and run IDs are in the protocol and receipts. Controls are
correctness tests, never estimates of natural relation yield. A single
ordinary query is a method gate, not a rate estimate.

## Reproduction and checks

All Sage jobs use the repository's checked launcher:

```sh
python3 experiments/compact-s3-m4-20261003/q1420_root_theory/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1420_root_theory/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/export_field.py --degree 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/export_field.py --degree 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/validate_root_field.py --degree 53 --samples 64
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/validate_root_field.py --degree 83 --samples 64
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/build_formula.py --degree 83 --kind ordinary --cell ordinary --preflight
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1420_root_theory/verify_archive.py --require-complete --emit
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

After protocol publication, execute each frozen cell with `run_stage.py`
through the same checked launcher. It records formula construction, CNF
shape, solver process, external-root arithmetic calls, memory, raw failures,
serialized CNF/model hashes, and exact-base group-law verification. An
independent checked-Sage replay is required before promoting a new ordinary
N83 relation as verified. CPU wall times from this unisolated host are
exploratory. Formula-building and callback operation counts are separate;
their weighted total, natural yield, final matrix, descent, and complete
degree-131 `2^x` remain unknown until measured or bounded.

## Frozen results

All six cells in the pre-registered run order completed, including two
preserved external timeouts. The [archive verifier](verification.json)
rechecked the serialized CNFs and every returned SAT model against both
omitted S3 pair links and the exact factor-base group relation.

| Degree | Cell | Status | Verified control relation | Formula build | Solver process | Peak child RSS | Root calls | External clauses |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 53 | full lock | SAT | 1 | 0.110 s | 0.306 s | 14.0 MB | 4 | 148 |
| 53 | free mids | SAT | 1 | 0.080 s | 0.134 s | 20.9 MB | 4 | 148 |
| 53 | ordinary | external timeout | 0 | 0.057 s | 60.014 s | 1,444.9 MB | unknown | unknown |
| 83 | full lock | SAT | 1 | 0.156 s | 0.120 s | 21.5 MB | 4 | 246 |
| 83 | free mids | SAT | 1 | 0.147 s | 0.243 s | 41.0 MB | 4 | 246 |
| 83 | ordinary | external timeout | 0 | 0.105 s | 60.006 s | 165.9 MB | unknown | unknown |

Times and decimal MB values above are exploratory observations on an
unisolated Darwin host. Each degree's two SAT rows recover the same archived
witness, so four verified cells are only two known relations reused as
controls. The `free_mids` cells validate the external-root mechanism with
fixed leaves. They do not test free-leaf search or natural relation yield.
The exact field API call counts for each N53 SAT cell are 116 multiply, 656
square, and 8 inverse inside the callback; each N83 SAT cell records 124,
1,016, and 8 respectively. Formula construction separately records
`n²` multiply and `n` square calls. The external timeout terminates the
ordinary solver process before it prints its callback counters, so those
counts are **unknown**, not zero. The N53 ordinary target is known to have
a relation from earlier work, but this solver did not recover it.

The result passes the known-witness mechanism gate and fails the ordinary
method gate at both degrees. It does not support an N53-to-N83 solve-growth
fit, a degree-131 per-query `2^x`, or a complete ECDLP projection. A next
version should stop gracefully at its cap and print search/conflict,
complete-pair, root, memory, and field-call counters; then test a sound
partial-pair or leaf-first search rule on the same archived ordinary targets.
That version needs a new frozen protocol and stage ID, leaving these six
receipts untouched.
