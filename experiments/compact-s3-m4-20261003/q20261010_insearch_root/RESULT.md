# Q1430: exact S3 pair roots enter CDCL search at N53 and N83

Q1430 implements an in-search external propagator for the two leaf-pair
links of the balanced four-summand S3 tree. When both leaf x coordinates
of a pair are assigned, it computes every exact middle-coordinate root
and adds guarded clauses immediately. On the ordinary N83 workload, the
unguided 5,000-conflict cell made 81 root queries, found 34 rootless pairs,
and added 7,670 clauses before its bound. This is the first measured
pre-model S3-root activity in this lane.

The predecessor Q1425 checked exact roots only after a complete SAT model.
Here CaDiCaL 3.0.1 calls the root oracle during CDCL search. A rootless
pair gives a conflict clause guarded by all 166 leaf bits at N83. One root
fixes each middle bit; two roots use one observed selector variable and
conditional middle-bit clauses. Every clause is valid for all assignments
matching the two leaves. The original three S3 links remain encoded in the
CNF, so the root clauses strengthen the search without changing its solution
set. The oracle is the existing `s3_root_oracle.py`, called through embedded
Python from the native CaDiCaL propagator.

## Frozen inputs and naming

| Degree | Curve ID | Workload ID | Normal-x weight bound | Actual usable base `B` | Folded columns `K` | Archived XCNF SHA-256 |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | `74f2979b3e68` | 3 | 24,062 | 227 | `62b5e4a47454c2cb08c716bc4b0eef51f0d1149dce61998e1ef8ddba1f008156` |
| 83 | `EC1N83Ckb1h876c2921cb64` | `bab50a1e5f66` | 5 | 30,977,592 | 186,612 | `ead520f8acf5509e37392ca71a5ee31de382fe1450e7e1ae63c0392cd9c0723b` |

The factor-base set digests, CNF hashes, source hashes, executable hash,
limits, and all raw solver output are in `measurements.json` and the adjacent
`.log` files. The comparison holds each degree's public point, complete raw
preimage coset, factor base, and balanced S3 tree fixed. `isogeny` is
`"none"`. Q1430 is a point-decomposition stage proposal; `candidate_id`
and `run_id` are null because the complete IC pipeline is not specified.

Native XOR rows were lowered with chained Tseitin XOR gates for the installed
CaDiCaL external-propagator API. Both ordinary XCNFs rebuild byte for byte
from their archives before lowering:

| Degree | Original variables | Original CNF clauses + native XOR rows | Lowered CNF variables | Lowered CNF clauses |
| ---: | ---: | ---: | ---: | ---: |
| 53 | 26,922 | 100,060 + 795 | 76,848 | 301,354 |
| 83 | 65,221 | 189,928 + 1,245 | 188,227 | 684,442 |

## Correctness checks

The archived known-solution controls solved with zero conflicts at both
degrees. The propagator issued two root queries and added 212 clauses at
N53 and 332 at N83. `verify.py` independently recomputed both S3 links
and matched all four archived leaf coordinates in each control. A separate
GF(2^11) check exhaustively evaluated all 2,048 third coordinates for the
rootless pair `(1, 3)`: the unconstrained CNF was satisfiable, while enabling
the propagator made it unsatisfiable after one exact root query.

## Ordinary search screen

`off` leaves the callback connected but disables root clauses. `none` uses
CaDiCaL's branching and enables roots. `first` asks the solver to complete
the first leaf pair; `all` asks it to complete all four leaves. All rows used
one thread, the same executable, a conflict cap, and an external wall cap.
The reported interval is CaDiCaL's `solve()` call after CNF parsing and
oracle initialization; it is a PDP stage diagnostic.

| Degree | Policy | Conflict cap | End | Conflicts | Root queries | Rootless pairs | External clauses | Solve wall s |
| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 53 | off | 1,000 | conflict | 1,001 | 0 | 0 | 0 | 13.28 |
| 53 | none | 1,000 | conflict | 1,001 | 0 | 0 | 0 | 7.14 |
| 53 | first | 1,000 | conflict | 1,001 | 1 | 0 | 53 | 14.04 |
| 53 | all | 1,000 | wall 30 s | 981 | 2 | 0 | 106 | 30.06 |
| 83 | off | 1,000 | conflict | 1,000 | 0 | 0 | 0 | 18.07 |
| 83 | none | 1,000 | conflict | 1,000 | 0 | 0 | 0 | 7.71 |
| 83 | first | 1,000 | conflict | 1,000 | 1 | 0 | 83 | 7.46 |
| 83 | all | 1,000 | conflict | 1,000 | 2 | 0 | 166 | 17.96 |
| 83 | off | 5,000 | wall 45 s | 2,747 | 0 | 0 | 0 | 45.16 |
| 83 | none | 5,000 | conflict | 5,000 | 81 | 34 | 7,670 | 15.80 |
| 83 | first | 5,000 | conflict | 5,000 | 2 | 0 | 166 | 31.55 |
| 83 | all | 5,000 | wall 45 s | 1,184 | 29 | 7 | 3,493 | 45.16 |

Every ordinary row is `BOUNDED_UNKNOWN`. The host load was approximately
80–140 during these runs and has no host-isolation receipt; wall ratios are
exploratory. The 5,000-conflict rows show that unguided branching eventually
exposes many complete pairs, while forcing all leaf decisions spends much of
its bound before useful conflict progress. The root clauses fire, but this
screen has no completed ordinary decomposition from which to compute natural
relation yield, rank novelty, field operations per completed solve, or a
complete N131 `2^x` work projection. Those fields remain null in the receipt,
as does the gap to the `2^61` challenge threshold.

## Reproduction and next experiment

From the repository root, build and prepare one N83 workload with:

```sh
sh experiments/compact-s3-m4-20261003/q20261010_insearch_root/build.sh /private/tmp/q1430_insearch
python3 experiments/compact-s3-m4-20261003/q20261010_insearch_root/prepare.py \
  --degree 83 --mode ordinary --output-prefix /private/tmp/q1430_ordinary
```

`prepare.py` also accepts degree 53 and `control` mode. Invoke `insearch`
with the generated CNF and map, source-module directory, field-module
directory, policy, conflict cap, and wall cap. Run `verify.py` on control
output and `validate_empty_root.py` on the binary. The exact source and
input hashes in `measurements.json` bind this run.

The next solver iteration should retain in-search roots while avoiding the
threefold CNF expansion and testing a branching rule that reaches diverse
leaf pairs early. The acceptance gate is an independently checked ordinary
relation on the exact N83 base, followed by measured natural yield and rank
novelty. Only then can the N131 per-decomposition cost be expressed in a
comparable field-operation `2^x` unit and charged into the single-target
total.
