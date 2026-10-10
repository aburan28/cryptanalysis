# Q1423 fixed-leaf S3 decomposition measurement

## Contribution

The four-summand equation is rewritten as a three-summand equation by selecting
one actual factor-base subgroup point `P3` outside the SAT solver and computing
`T = Q - P3`. The SAT formula has three leaves, one intermediate x coordinate,
and two factored S3 links. This measures the effect of removing one full leaf
and one link from the ordinary-query formula.

## Exact instances and naming

`Q1423` is a stage proposal; `candidate_id`, `run_id`, and complete-solve costs
are null until the relation collector, rank, final LA, and target recovery are
specified and measured. `ISO0` is represented as `isogeny: none`.

| Field | Curve ID | Exact factor base | B before folding | Folded columns K | Ordinary workload |
| --- | --- | --- | ---: | ---: | --- |
| N53 | `EC1N53Ckb1hf77aab617904` | Q1301 normal-x W<=3 subgroup orbit base | 24,062 | 227 | `74f2979b3e68` |
| N83 | `EC1N83Ckb1h876c2921cb64` | Q1325 projected normal-x W<=5 complete base | 30,977,592 | 186,612 | `bab50a1e5f66` |

N53 leaf selectors choose exact subgroup x orbits and Frobenius shifts. N83
raw x leaves have normal-basis weight at most five and are projected by
cofactor four. Four x coordinates of the preimage coset for `T` are selectable
inside SAT. All solutions must pass exact group-law sign lifting, subgroup
membership, base membership, and `P0+P1+P2+P3=Q` replay.

## Frozen cases

Use the existing N53 ordinary relation and Q1325 N83 seed-830525 fixture as
known-solution controls. A locked formula pins the three variable leaves and
the intermediate. An unpinned control retains the same fixed point and public
target with all three leaves free. Ordinary cases use their frozen public
points with two deterministic fixed-point policies:

* `pool1`: select the first SHA-256 derived orbit point.
* `pool64`: derive 64 orbit points and choose the one minimizing normal-basis
  weight of `x(Q-P3)`, breaking ties by `x(Q-P3)` and candidate index.

All 64 group subtractions in `pool64` are charged to target query time. This
guided policy is target-dependent; the Q1422 nonadaptive fixed-list bound does
not apply to its choice without a separate argument.

CryptoMiniSat runs one thread with deterministic random seed zero and at most
1,000,000 conflicts. The locked control has 30 solver seconds and a 40-second
external cap; the unpinned and ordinary cases have 120 solver seconds and a
135-second external cap. RSS cap is 1,536 MiB. A capped search is recorded
as `BOUNDED_UNKNOWN`. The `.xcnf`, stdout, and stderr are archived with hashes.
Formula construction, target point selection, SAT search, and relation checks
are measured separately. Startup and exact base loading are separate.

## Decision gate

Count a natural relation only after exact replay and base membership. Report
ordinary yield as censored when the capped runs are unresolved; do not infer
an N131 per-decomposition field-operation rate from SAT conflicts or time.
Compare formula size and locked/unpinned search behavior against the same
target Q1373/Q1404/Q1419 receipts. A complete N131 cost `2^x` requires the
base, relation yield, novel-rank rate, collector, matrix solve, and target
descent under a common operation boundary; retain it as null until available.
