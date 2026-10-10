# ECC2K-130 ternary-XOR CNF bridge: paired controls pass, ordinary Q0 search remains bounded

Every native XOR in the frozen `wz_only` Q1420 source and degree-263
descendant formulas has three signed literals. Replacing each XOR with its
four truth-table CNF clauses preserved the original variable count. Both
fixed-witness z0 controls returned SAT under Kissat 4.0.4, and their models
satisfied every archived ordinary clause and native XOR. Both matched
ordinary public-query cells entered search and returned `s UNKNOWN` at the
precommitted 120-second Kissat limit. The [independent audit](runs/R1/audit.json)
rebuilt all four inputs from pinned Git objects, checked every converted CNF
hash and raw transcript, and replayed both SAT models.

The input commit is `abd1b14f1f763602e5444b5acbb58f7d3f1412c4`;
the [protocol](PROTOCOL.md), [source manifest](source.json), converter and
runner were committed and pushed as `e02d8267c` before the guarded runs.
The source and descendant each use the exact Q1420 W24 base with
`B=16,772,828` subgroup-usable points and the same public-query index zero
of workload `eee7f6ee5f6b`. The verified route is
`IW1E263d1hadee4e69fa3d`. This is a PDP-stage record with
`candidate_id: null`.

| Cell | Variables | CNF clauses | Status | Solver wall s | Process CPU s | Peak sampled RSS MiB | Search conflicts |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Source fixed z0 | 345,702 | 1,260,827 | `SAT_XCNF_MODEL_VERIFIED` | 4.878 | 0.948 | 60.70 | — |
| Descendant fixed z0 | 350,141 | 1,278,577 | `SAT_XCNF_MODEL_VERIFIED` | 2.475 | 0.825 | 61.58 | — |
| Source ordinary Q0 | 367,382 | 1,332,136 | `BOUNDED_UNKNOWN` | 121.169 | 19.077 | 344.98 | 19,323 |
| Descendant ordinary Q0 | 372,360 | 1,351,844 | `BOUNDED_UNKNOWN` | 120.207 | 10.084 | 357.83 | 10,057 |

The source ordinary formula contains 397,300 ordinary clauses and 233,709
ternary native XORs. Its descendant counterpart contains 397,336 and
238,627 respectively. The CNF bridge emits four clauses per XOR, so the
paired ordinary formulas have the counts above without auxiliary variables.
The converter checks all eight truth values under all eight input-sign
patterns and validates literal ranges, header counts and output SHA-256.
Kissat binary SHA-256 is
`05d6f3e9c402a1fe8853b0746e384e1b3d1c4a550e255f11daa2461d279aa848`.

Both SAT controls replayed all original constraints: 359,527 ordinary
clauses plus 225,325 native XORs on the source, and 358,969 plus 229,902 on
the descendant. The source ordinary transcript records 602,128 decisions;
the descendant records 506,382. Each ordinary result is a capped search,
with no emitted group relation or rank row. The archived native-XOR
CryptoMiniSat `wz_only` ordinary cells are the same-input reference and
also recorded `BOUNDED_UNKNOWN` at their separate caps. Neither run pair
provides a controlled solver timing ratio: the local host had no isolation
receipt, and the Kissat children received only 19.077 and 10.084 CPU seconds
within roughly 120 wall seconds. Formula conversion and input preparation
are separately recorded and excluded from the solver interval.

The [raw receipts](runs/R1) retain compressed stdout, stderr, source,
protocol, converter, runner, original XCNF, unit-delta and converted-CNF
hashes, exit codes, caps, CPU time, and RSS. The 4-GiB RSS and 150-second
external ordinary wall guards did not fire. The next decision is to compare
native-XOR and CNF policies in an isolated paired environment before using
wall time to choose a solver. An ordinary verified relation and its novel
rank contribution remain the gate for the 16/256-query equal-useful-size
screen; the selector/x-inverse coupling isolated by the preceding bilinear
tests is a separate algorithmic target.

Replay the archive-only audit from a checkout containing the pinned input
commit:

```sh
python3 experiments/ecc2k130-xcnf-kissat-bridge-20261010/audit.py \
  --out /private/tmp/ecc2k130-xcnf-kissat-audit-replay.json
cmp /private/tmp/ecc2k130-xcnf-kissat-audit-replay.json \
  experiments/ecc2k130-xcnf-kissat-bridge-20261010/runs/R1/audit.json
```
