# Q1425 incremental external S3 root lemmas

## Contribution

Q1425 retains four variable factor-base leaves in a balanced S3 tree. It
keeps the outer S3 link as a native-XOR SAT constraint and defers one or
both pair links to an exact field root oracle. CryptoMiniSat's incremental
C API keeps learned clauses across calls. When SAT returns a complete
candidate, the oracle computes all roots of each deferred
`S3(x2j,x2j+1,uj)=0`; a conditional CNF lemma restricts that precise leaf
pair to its zero, one, or two valid roots. The model is accepted only after
all three S3 links and the exact four-point group sum replay. The
`ordinary_left_lazy` cell retains the right-pair SAT link as a comparator.

This is a bounded, model-triggered refinement of a full four-leaf system.
The oracle fires on complete SAT models rather than partial assignments;
its measured root calls and lemmas test whether this weaker coupling is
useful before building a solver with partial-assignment callbacks.

## Exact inputs and naming

Q1425 is a PDP proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: none` (`ISO0`). N53 uses curve
`EC1N53Ckb1hf77aab617904`, the Q1301 cofactor-projected W≤3 base with
`B=24,062` actual subgroup points and `K=227` signed-Frobenius columns.
Its ordinary workload is `74f2979b3e68`. N83 uses
`EC1N83Ckb1h876c2921cb64`, the exact Q1325 projected W≤5 base with
`B=30,977,592`, `K=186,612`, and ordinary workload `bab50a1e5f66`.
The exact base digests, curve records, public points, preimage sets, source
hashes, and CryptoMiniSat library hash are frozen in `freeze.json`.

The N53 known-solution control reuses Q1419's pinned Q1410 ordinary
representation. The N83 control reuses Q1419's pinned Q1408 planted
representation. Both controls pin only the four raw leaf x coordinates and
target-preimage selector; the pair intermediates remain free. Exact root
lemmas for both fixed pairs are inserted before the first SAT call. Ordinary
queries have all four leaves and both pair intermediates free and insert
root lemmas only for candidate models returned by SAT.

## Lemma and validation

For nonzero fixed `a,b`, the existing `s3_root_oracle.py` returns all field
roots of `S3(a,b,u)=0`. Let `M(a,b)` be a disjunction of mismatch literals
for the two leaf vectors. For zero roots, add `M`; for one root, add one
`M or (u_j=root_j)` clause for each bit. For two roots, introduce one fresh
branch bit and use conditional bit clauses for both roots, sharing clauses
where their bits agree. Thus the lemma is vacuous for other leaf pairs and
exact for the selected pair. `test_lemma.py` exhausts all 961 nonzero pair
inputs and every possible intermediate over `GF(2^5)`, comparing the oracle
and the CNF truth condition to direct S3 evaluation.

Every SAT model is checked against the original CNF/XOR rows and all added
lemmas. A candidate satisfying the deferred link is checked by exact
factor-base membership, subgroup projection, four distinct folded columns,
and signed group sum. New ordinary relations require independent checked
Sage replay and rank-novelty measurement before promotion.

## Frozen resource and accounting boundary

Each case has at most 90 target-dependent wall seconds, 17 incremental
solver calls, 16 root refinements, 100,000 conflicts and 25 CPU seconds per
solver call, and 1,536 MiB RSS. One SAT thread is used. The runner saves
every solve-call state, candidate pair, root count, lemma digest, status,
timing, memory, and the exact root-oracle API call vector. The library C API
does not expose exact per-call conflict counters; those stay null rather
than being inferred from the cap. Inversions are counted as one field API
call and are not expanded into a common field-operation unit. Formula build,
solver load, root work, search, and relation check have separate clocks.

The `pilot_v1` archive retains the first left-only control attempt: N53
stopped after 100,000 conflicts and 5.032 seconds with one preseed lemma.
That pilot's runner then asserted because it incorrectly required every
control to succeed. Its trace and original freeze are preserved; it is not
one of the v2 result cells. The v2 runner records bounded controls normally.

`BOUNDED_UNKNOWN` means the stopped search remains unresolved. Locked
controls measure correctness and search behavior, not ordinary yield. CPU
wall-time ratios are exploratory without a host-isolation receipt. Natural
yield, cost per useful row, final matrix cost, target descent, and complete
N131 cold and one-target-online `2^x` fields remain unknown until directly
measured under a common accounting boundary.
