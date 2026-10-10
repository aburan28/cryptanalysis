# Q1428: two external root links, one fixed-output right-pair SAT link

Q1427's anchored N53/N83 controls and ordinary queries stayed bounded
while SAT handled the right-pair and outer S3 links together. Q1428
computes the outer roots exactly too. For each exact-base anchored pair
`(x0,x1)`, the first oracle yields every `u` satisfying `S3(x0,x1,u)=0`.
For each raw public-target lift `t`, the second oracle yields every `v`
satisfying `S3(u,t,v)=0`. One SAT formula asks for two nonzero,
normal-basis-weight-bounded leaves `(x2,x3)` satisfying
`S3(x2,x3,v)=0`, with `v` supplied as an assumption. The same solver
instance and its learned clauses serve all `u`, `t`, and `v` branches of
an anchor. The exact group sum, subgroup, base membership, and distinct
folded columns are checked on every returned model.

This is a full four-summand decomposition method when all anchored pairs
and raw target lifts are searched and charged. The bounded experiment
reuses Q1427's exact N53/N83 curves, bases, frozen controls, two
witness-independent ordinary anchors at each degree, and lift schedule:
two of 428 N53 lifts and all four N83 lifts are scheduled, subject to the
per-anchor stop. A stopped schedule is an incomplete target query. The
proposal remains `Q1428`, `candidate_id: null`, `run_id: null`, and
`isogeny: "none"` (`ISO0`). N53 is `EC1N53Ckb1hf77aab617904`, Q1301
W≤3, B=24,062/K=227, workload `74f2979b3e68`; N83 is
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, B=30,977,592/K=186,612,
workload `bab50a1e5f66`. Exact IDs and digests are frozen in
`freeze.json` before any measured SAT call.

The known-solution controls pin the right pair only in a separate
correctness test. Their measured cells supply the known left pair and
public target lift, with both right leaves free. Ordinary anchors are
regenerated from the deterministic exact-base selector and charged as
target-dependent query work. The anchor base archive is loaded as
reusable preparation and charged separately in cold accounting. Root
field API calls, formula work, SAT calls, exact conflicts,
propagations, decisions, memory, and every rejected model are retained.

One SAT thread is used. Each anchor has a 90-second target-dependent
wall limit, 17 SAT calls, and 16 rejected complete models. Each call
has configured caps of 100,000 conflicts and 25 CPU seconds. A
`BOUNDED_UNKNOWN` branch remains censored. New N83 ordinary relations
require independent checked-Sage replay and rank-novelty measurement.
CPU wall-time ratios are exploratory without an isolation receipt.

The complete N131 `2^x` work estimate stays null until ordinary
relation yield, cost per useful row, matrix construction and final
linear algebra, target descent, and replay are charged in one unit.
