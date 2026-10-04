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
