# Full SAT models decode the Q1420 cancellation branch on both curves

The complete native-XOR projective-S3 circuit admits the archived
six-summand cancellation witness on the ECC2K-130 source and degree-263
descendant-native curves. Each fully fixed control produced a CryptoMiniSat
SAT model; an independent checker replayed **every ordinary clause and native
XOR**, decoded its six factor-base leaves and four projective intermediates,
and found leaf signs whose exact group sum equals the archived target point.
Changing the target x coordinate's low bit while keeping the witness fixed
returned explicit UNSAT on both curves. The two controls with only the leaf
masks fixed reached their 120-second internal cap with `BOUNDED_UNKNOWN`.

This is an exceptional-branch extraction correctness gate for the
[projective chart](../ecc2k130-263-projective-s3-20261010/RESULT.md). Its
target is the archived cancellation witness, not the public Q1420 target.
The six cells use `B=16,772,828` subgroup-usable points per policy and the
same source/descendant leaf equations as the parent. Both control builders
first reproduced the parent projective formula's raw SHA-256 byte for byte;
they then replaced only the four target mux x choices with
`(witness_x, witness_x xor 1, witness_x xor 1, witness_x xor 1)`.

| Curve policy | Control base vars / clauses / XORs | Fixed SAT: wall / child peak RSS / independently checked clauses + XORs | Bit-mutated status / wall | Free-intermediate status / wall / child peak RSS |
| --- | ---: | ---: | ---: | ---: |
| Source W24 prefix | 340,821 / 334,948 / 227,932 | 0.515 s / 135,692,288 B / 337,194 + 227,932 | `UNSAT` / 0.259 s | `BOUNDED_UNKNOWN` / 122.340 s / 383,533,056 B |
| Descendant-native W24 | 345,266 / 334,390 / 232,515 | 0.258 s / 138,117,120 B / 336,636 + 232,515 | `UNSAT` / 0.264 s | `BOUNDED_UNKNOWN` / 121.717 s / 380,665,856 B |

The fixed controls each append 2,246 unit clauses for the six masks, leaf
coordinates, intermediate coordinates/finite flags, and target selector.
The free-intermediate cells append 146 units for just the masks and target
selector; all leaf coordinates and intermediate states remain solver
variables. Both verified SAT models admit two leaf-sign assignments matching
all four decoded intermediate x classes and the exact archived target point.
The source and descendant negative cells exited 20 with `s UNSATISFIABLE`;
the free cells exited 15 with `s INDETERMINATE`. All six used the pinned
CryptoMiniSat 5.14.7 binary, one thread, a 4-GiB external RSS guard, and
their frozen 45/60-second fixed or 120/150-second free internal/external wall
caps. No external guard fired. The host has no CPU-isolation receipt, so the
wall figures are exploratory stage costs. `candidate_id`, natural relation
yield, novel rank, single-target online IC time, and matched rho ratio are
null in [R1/audit.json](runs/R1/audit.json).

The [protocol](PROTOCOL.md) and source were committed and pushed before
solver outcomes. The two exact control-base XCNFs and all six raw solver
stdout streams are losslessly archived; each solved input is reconstructed
from one base XCNF plus an ordered unit-clause delta, with the header count
adjusted and its raw SHA-256 checked. The [independent auditor](audit.py)
passes using only those archives and deltas. It checks all source/input and
binary hashes, build/solver guards, terminal statuses, every clause/XOR in
the two SAT models, and an independent binary group-law replay. The first
audit invocation's full-disk scratch failure and subsequent scratch-placement
repair are recorded in [AUDIT_AMENDMENT.md](AUDIT_AMENDMENT.md); no solver cell
was repeated. Fast-cell `ps` samples can undercount a short-lived process,
so the table reports the child `ru_maxrss` peaks. Construction guards passed
at 4.138 s / 295,731,200 B source and 4.183 s / 303,710,208 B descendant.

The next PDP experiment should release one witness block at a time: first
hold leaf masks and x/z coordinates while leaving only the four projective
intermediates free, then hold masks and intermediates while leaving leaf
coordinates free. Pair those two cells on the same control target and caps.
That isolates which unknown block turns the half-second verified circuit
into a bounded two-minute search. Only after that diagnosis should an
ordinary-query finite/projective comparison run with one frozen public point,
identical Gaussian settings and resources, charged failed attempts, and
verified relation/rank output.

Reproduce the audit from compressed evidence:

```sh
python3 -B experiments/ecc2k130-263-projective-s3-sat-20261010/audit.py \
  --run-dir experiments/ecc2k130-263-projective-s3-sat-20261010/runs/R1 \
  --out /private/tmp/ecc2k130-projective-s3-sat-audit-replay.json \
  --scratch-dir /private/tmp
cmp /private/tmp/ecc2k130-projective-s3-sat-audit-replay.json \
  experiments/ecc2k130-263-projective-s3-sat-20261010/runs/R1/audit.json
```
