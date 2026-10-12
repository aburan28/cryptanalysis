# Q1519: exact N53 second-pair lookup finds the frozen positive complement

An exact full-base lookup recovered the two remaining factor-base points for
the frozen positive N53 complement after **10,390 pair probes**. The query
made **10,390 public field inversions and 20,780 public field
multiplications**; the latter is \(2^{14.343}\) calls. Independent group and
archived-orbit replay checks the witness. The field API categories are
nested and must not be summed into one operation total.

This is a `PDP4mitm` stage measurement under proposal `Q1519`, with null
candidate and run IDs and `isogeny: "none"`. Its exact curve is
`EC1N53Ckb1hf77aab617904`. The normal-basis weight-three subgroup base has
**B=24,062** distinct usable points and **K=227** signed-Frobenius columns;
the enumerated-point digest is `356ebb34476f44b89d376e04fe4b03570a0a4cf3dfe0cd722309d7ea083ccc18`.
The query input is the unpinned x-complement `8953252913413885` from the
frozen Q1513 known-positive relation. The recovered x coordinates are
`5653674987373494` and `4926914798828727`, matching the independent
Q1513 pinned correctness control. The [direct protocol](direct_protocol.json),
[receipt](direct_result.json), and [validator](direct_validate.py) retain exact
source/input hashes, every failed probe before the match, operation counts,
and a group-law replay. The archived canonical x-orbits independently confirm
both leaves belong to the exact base.

| Stage | Exact result | Exploratory wall |
| --- | ---: | ---: |
| Rebuild exact base, target-independent | 24,062 points; digest matched | 165.11 s |
| Query one known-positive complement | 10,390 failed/successful probes; 10,390 inversions and 20,780 multiplications | 3.55 s |
| SAT on the same unpinned S3 formula | Eight settings reached `WALL_CAP`; no completed setting | 15 s outer cap per setting |

The SAT panel froze one 4,246-variable, 15,144-CNF, 365-XOR formula with SHA-256
`7644b17ed9524770d4f03a79b025342eda5e6c63137b6c987563b9d542f2cc7b`.
It swept five polarities, a second random seed, and Luby/geometric restarts
under a 1.5-million-conflict limit, 10-second soft CPU limit, and 15-second
outer wall cap. All eight rows ended at `WALL_CAP`; child user CPU ranged
from 1.84 to 6.38 seconds under host contention. Exact conflicts at
termination were unavailable. The pinned Q1513 formula has a verified SAT
model, so these capped unpinned rows are censored. The [SAT protocol](protocol.json),
[per-setting receipts](runs), [analysis](analysis.json), and
[validator](validate.py) preserve each status and raw solver output. The
different accounting boundaries and unisolated host do not support a wall
speedup ratio between the scan and SAT panel.

The direct lookup makes the second-pair handoff concrete at N53. Its linear
scan still scales with the actual base size; the existing N131 independent
uniform first-pair scan model remains \(2^{123.289}\) batch multiplication
calls for relation supply, **62.289 bits above \(2^{61}\)**. This is a model
for a specified stage, with no measured N83 natural relation yield or rank
novelty for Q1519. The complete charged N131 solve exponent stays null.
The next useful experiment is an indexed or target-conditioned second-pair
query on the exact N83 base, paired on the frozen selected and holdout
ordinary points. It should record every first-pair rejection, exact-base
relation, novel matrix row, and operation count before extrapolating.

Recheck the archived receipts and witness with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1519_second_pair_sat_sweep/validate.py
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1519_second_pair_sat_sweep/direct_validate.py
```
