# Compact four-summand S3-chain probe

This experiment tests one point-decomposition stage of ECC2K-130 index
calculus. It uses three compact S3 links and two free intermediate x
coordinates, so it does not expand S5. The experiment is **not** a complete
ECDLP solver. The frozen ordinary n=53 and n=83 SAT queries both exhausted a
20-second target-PDP cap without a model. A follow-up corrected the target
coverage to include **all** raw preimages under the curve cofactor; those
ordinary queries also remained censored. Consequently there is no measured
degree-131 complete-solve work exponent, and no sub-\(2^{61}\) claim.
Later probes also covered every Frobenius conjugate of those preimages and
tested ordered leaves; neither produced an unassisted ordinary relation.
An exact subgroup-base-orbit encoding then tested the public target directly.
Its known-satisfiable n=53 ordinary query reached one million conflicts
without a model, and its n=83 planted and ordinary queries reached the
120-second cap without a model. Locked witness controls passed where a
witness is known.
An exact, larger n=83 weight-five base later passed a fully locked control,
but its unassisted ordinary target also reached a 120-second cap without a
model. The larger base changes the factor-base policy; it is recorded as
Q1324 with its own exact digest.
A complete n=83 weight-at-most-five base, Q1325, was then enumerated and
independently replayed. Its locked control passed, while the same ordinary
public target again reached a 120-second cap without a model. The full base
is denser than Q1324's selected base, but neither result supplies an
ordinary four-point relation or a complete DLP cost.
A second n=83 encoding represents the same exact base implicitly through
cofactor-four projection of sparse rational x values. It reduced the CNF
clause count but also produced no unassisted relation within its caps.
An exact half-trace root circuit for the first two S3 links was tested next;
its ordinary n=83 query also remained censored.
A full point-addition circuit then made the intermediate sums deterministic
once all four leaf points were fixed. Its unassisted n=53 and n=83 queries
also remained censored at 120 seconds.
A subsequent native S3 root index recovered an unpinned ordinary n=53
relation on the same exact base and public target. Its bounded n=83 run
exhausted a 2,000,000-state cap without a relation. These are stage results;
neither supplies a complete discrete-logarithm work exponent.

## Identity and comparable inputs

[`protocol.json`](protocol.json) freezes the original curve, subgroup,
weight-base policy, one-target ordinary workload, and SAT cap. Q1301 and
Q1302's exact enumerated bases are in `bases/`; their compact archives
contain every canonical signed-Frobenius x-orbit key and its length.
[`verify_weight_base.py`](verify_weight_base.py) checks archive structure,
orbit arithmetic, counts, and sampled subgroup membership. Q1324 uses the
separately frozen selected weight-five point base; Q1325's full point-key
archive is in `bases/`. The n=53 pair-table comparator independently
recomputes its original orbit-key digest.

| Proposal | Exact curve ID | Weight policy | Actual usable points \(B\) | Folded columns | Base-key SHA-256 prefix |
| --- | --- | ---: | ---: | ---: | --- |
| Q1301 | `EC1N53Ckb1hf77aab617904` | 3 | 24,062 | 227 | `05b75578ee58` |
| Q1302 | `EC1N83Ckb1h876c2921cb64` | 4 | 1,934,066 | 11,651 | `800a59307125` |
| Q1324 | `EC1N83Ckb1h876c2921cb64` | selected 5 | 4,000,102 | 24,097 | `e6ea595bbd32` |
| Q1325 | `EC1N83Ckb1h876c2921cb64` | all ≤5 | 30,977,592 | 186,612 | `56c951ad78cc` |
| Q1303 | `EC1N131Ckb1h6816f880945e` | proposed 6 | unknown | unknown | unknown |

The exact n=53 curve cofactor is **428**; the n=83 and n=131 cofactors are
**4**.
These values are read from the curve manifests when constructing raw target
preimages and subgroup points. All listed designs use `isogeny: "none"`. They
remain `Q` proposals with `candidate_id: null` because relation collection,
final relation-matrix LA, target descent, and complete recovery are not wired
or measured. A base size or nominal weight bound is not an `IC1` candidate ID.

## Compact SAT stage

[`chain_s3.py`](chain_s3.py) emits a native-XOR XCNF for three S3 links:
\((uv+uw+vw)^2+uvw+1=0\). Leaf x coordinates have normal-basis Hamming
weight at most the frozen bound; two intermediate x coordinates are free.
The runner tries curve lifts and sign choices, and checks the raw four-point
sum and cofactor-projected public target before accepting a relation.

The n=5 planted control solves and its four lifted points sum to its target.
At n=53 and n=83, the runner independently checks that each planted witness
satisfies the S3 equations, then both planted and ordinary formulas time out.
Thus the full-size planted tests check formula construction but do not show
that CryptoMiniSat can recover a witness at those sizes. All ordinary results
are single-target stage diagnostics, not online DLP timings.

| Curve | Workload ID for ordinary query | Planted status | Ordinary status | Ordinary formula (vars / CNF / XOR) | Charged target-PDP wall |
| --- | --- | --- | --- | --- | ---: |
| n=53 | `74f2979b3e68` | censored at 20 s | censored at 20 s | 26,860 / 77,292 / 795 | 20.071 s |
| n=83 | `bab50a1e5f66` | censored at 20 s | censored at 20 s | 64,808 / 188,944 / 1,245 | 20.168 s |

The original circuit fixes one raw subgroup preimage of the public target.
For n=53, that is only **one of 428** raw targets whose cofactor projection
is the same public point; for n=83 it is one of four. This makes the original
SAT stage a narrower diagnostic than the matched pair-table public-target
search. The correction below closes that comparison gap.

The four frozen receipts, gzip-archived XCNFs, and solver logs are in `runs/`
with names `n{53,83}_{planted,ordinary}_frozen.*`. The archive verifier
decompresses each formula and checks its exact SHA-256 and byte count against
the receipt. A timeout is neither UNSAT nor an
observed zero natural-relation rate. The solver produced no model and no
field-operation count before the cap. Failed attempts are charged to the
target-PDP stage. The checked Sage runtime snapshot used for measured local
jobs is [`sage_runtime_info.json`](sage_runtime_info.json).

## Full cofactor-preimage SAT stage

[`cofactor_preimages.py`](cofactor_preimages.py) enumerates the complete
kernel of multiplication by the exact curve cofactor and constructs every
raw point mapping to each frozen public target. It found 428 distinct raw
x coordinates at n=53 and four at n=83. The enumeration checks every point
under the cofactor map. [`chain_s3_multitarget.py`](chain_s3_multitarget.py)
adds a selector so one S3 chain can choose any of those raw target points.
Its links use the equivalent three-product identity
\(ab+ac+bc=ab+(a+b)c\).

The matched n=53 pair-table relation was lifted back to four raw weight-three
leaves. Their raw sum is **preimage 201**, whereas the original frozen SAT
query fixed a different preimage. With those four leaves and the two
intermediate x coordinates locked, the full n=53 formula returns SAT and
reconstructs the correct public relation. The full-size planted n=53 and
n=83 controls also return SAT when their witness coordinates are locked.
These controls verify the encoding; they are not natural solver successes.

| Public target | Raw preimages allowed | Ordinary formula (vars / CNF / XOR) | Ordinary bounded result | Longer diagnostic |
| --- | ---: | --- | --- | --- |
| n=53, Q1306 | 428 | 26,922 / 100,060 / 795 | 100,002 conflicts, 11.57 s, no model | 1,000,002 conflicts, 84.15 s, no model |
| n=83, Q1307 | 4 | 64,893 / 189,276 / 1,245 | 20.11 s wall cap, no model | 100,002 conflicts, 23.79 s, no model; solver displayed about 145M propagations |

The longer diagnostics reuse a precomputed formula, so their wall intervals
exclude formula construction. The bounded runs charge formula construction
and all attempts. Neither query produced a natural relation. Conflict counts
and SAT propagations are solver-specific Boolean work units; they are not
field-operation equivalents. The cofactor-coset construction is recorded
separately and must be charged under target-query preparation in any
one-target online study. Formula and log receipts are in `runs/`; the checked
runtime snapshot is `factored_sage_runtime_info.json`.

[`chain_s3_factored.py`](chain_s3_factored.py) also tests the three-product
identity with one fixed raw target. It reduced n=53 AND gates from 25,281
to 19,663, but reached the 100,000-conflict cap without a model. Allowing
the target to vary restores nonlinear products in the final S3 link; the
complete n=53 preimage formula uses 25,281 AND gates. Formula size reduction
alone did not establish a useful decomposition solver.

An additional n=53 variant, Q1308, precomputes all 12,826 nonrational
weight-at-most-three x supports and forbids those exact leaf assignments.
[`chain_s3_rational.py`](chain_s3_rational.py) retains the 12,031 rational
supports and the same 428 raw target preimages. The known ordinary relation
at preimage 201 still solves when locked. In the unassisted ordinary run,
the filter increased the formula to 151,364 CNF clauses and reached 100,002
conflicts in 18.81 s without a model; the unfiltered complete-preimage run
reached the same conflict cap in 11.57 s. These are single runs, so the
timing difference is a diagnostic, not a stable speed ratio. The planted
filtered run also exhausted its wall cap. The exact support archive and
receipts are retained as a negative solver variant.

## Frobenius target orbit and ordered leaves

[`chain_s3_orbit.py`](chain_s3_orbit.py) adds a compact Frobenius shift to
the complete cofactor-preimage selector. This admits all **22,684** distinct
raw target x coordinates at n=53 (428 preimages times 53 shifts) and **332**
at n=83 (4 times 83). Q1309 and Q1310 name these stage proposals. The
base, public point, and workload remain exactly the same as in the full
preimage comparison. The extra targets are equivalent under the Frobenius
action on this base; their count is not an independent relation-yield
multiplier.

[`chain_s3_ordered.py`](chain_s3_ordered.py) also requires the four leaf x
coordinates to be in nondecreasing numeric order, removing their permutation
symmetry. Q1311 and Q1312 name the n=53 and n=83 ordered proposals. Exhaustive
small-bit tests check the comparator. At full size, the known n=53 ordinary
four-point relation and the planted n=53/n=83 relations solve with their
coordinates, preimage, and Frobenius shift locked. Each locked result maps
back to its original public target. The leaves are shifted before sorting,
because numeric order is not Frobenius invariant. These are encoding controls,
not unassisted solver successes.

| Curve and target | Orbit target choices | Orbit result | Ordered result |
| --- | ---: | --- | --- |
| n=53 ordinary, known satisfiable | 22,684 | 20.13 s wall cap; no model | 100,001 conflicts in 15.27 s; no model |
| n=53 planted | 22,684 | 100,002 conflicts in 16.68 s; no model | 20.45 s wall cap; no model |
| n=83 ordinary | 332 | 20.12 s wall cap; no model | 20.10 s wall cap; no model |
| n=83 planted | 332 | 20.12 s wall cap; no model | 20.39 s wall cap; no model |

The n=53 ordinary orbit formula also reached **1,000,002 conflicts** in
86.08 s with its formula precomputed and returned no model. That case has
a known raw relation, so the run measures a censored search on a satisfiable
instance, not mathematical nonexistence. Formula construction and all
failed attempts are charged in the bounded stage receipts; the extended
solver-only interval is labeled separately. Solver conflicts are Boolean
events and have no established field-operation conversion. These runs do
not support a degree-131 \(2^x\) complete-solve estimate.

The source-bound receipts, exact solver logs, and verified gzip XCNFs are
in `runs/`. Checked Sage runtime snapshots are
`orbit_sage_runtime_info.json` and `ordered_sage_runtime_info.json`.
Relation receipts store `projected_points` as the unsigned cofactor
projections of x lifts and store their signs separately; the sign must be
applied before adding or mapping projected points back by Frobenius.

## Fixed known-witness target diagnostic

[`run_fixed_witness_target.py`](run_fixed_witness_target.py) removes the
cofactor selector and Frobenius barrel from the solver formula, then fixes
just one raw target x coordinate. For n=53, it selects **preimage 201** using
the relation independently found by the pair table. For n=83, it uses the
planted fixture's raw target. These are Q1313 and Q1314 stage diagnostics,
with `candidate_id` and `workload_id` both null; selecting a known-satisfiable
n=53 preimage is oracle assistance and is not an ordinary public-target yield
or online IC measurement.

| Diagnostic | Formula vars / CNF / XOR | Unassisted search | Post-run locked control |
| --- | --- | --- | --- |
| n=53 known ordinary relation, preimage 201 | 21,242 / 60,438 / 795 | 1,000,001 conflicts, 119.48 s charged PDP; no model | SAT, exact raw/public relation verified |
| n=83 planted raw target | 51,030 / 147,610 / 1,245 | 100,002 conflicts, 24.23 s charged PDP; no model | SAT, exact raw/public relation verified |

Each charged PDP interval includes formula construction and the unassisted
solver call; the locked control runs afterward and is reported separately.
The formulas, solver logs, checked Sage runtime snapshot, and receipts are
source-bound and archive-verified. Removing target selection did not recover
either witness within these caps. The result locates a solver search
bottleneck in the core chained-S3 formula; it does not establish a lower
bound on every solver or prove that a raw target lacks a decomposition.

## Exact subgroup-base-orbit SAT stage

[`chain_s3_base_orbit.py`](chain_s3_base_orbit.py) selects each leaf from the
**exact archived subgroup factor base**: one canonical signed-Frobenius
x-orbit key plus a Frobenius shift. The SAT formula uses the x coordinate of
the public subgroup point directly. This avoids both the raw cofactor-
preimage selector and sparse x assignments that do not lift into the usable
base. Four leaf choices are ordered by `(orbit index, shift)`; all sign
choices and the final group sum are checked after a model. The same curve,
public point, base digest, and workload IDs are retained. These variants
are Q1315 at n=53 and Q1316 at n=83, with `candidate_id: null` and
`isogeny: "none"`.

| Stage query | Exact base B / folded columns | Formula vars / CNF / XOR | Unassisted result | Charged target-PDP wall | Post-run locked control |
| --- | ---: | --- | --- | ---: | --- |
| n=53 ordinary, known satisfiable | 24,062 / 227 | 23,055 / 72,902 / 1,037 | 1,000,001 conflicts, no model | 33.30 s | SAT; public relation replayed |
| n=83 planted | 1,934,066 / 11,651 | 99,036 / 872,878 / 1,632 | 120 s cap, no model | 120.04 s | SAT; public relation replayed |
| n=83 ordinary | 1,934,066 / 11,651 | 99,036 / 872,878 / 1,632 | 120 s cap, no model | 120.02 s | no witness available |

The charged interval starts at target-dependent formula construction and
includes the unassisted solver call; the locked controls run afterward. The
n=53 control uses the independent pair-table relation. The n=83 planted
control uses four projected subgroup leaves from the frozen fixture. Neither
control measures unassisted solver success. The n=83 ordinary target may
have no representation in the base; one capped query cannot determine that.
No row establishes a natural relation yield, field-operation conversion, or
complete ECDLP solve cost. Source-bound receipts, solver logs, and gzip XCNFs
are in `runs/`, with the checked runtime snapshot at
`base_orbit_sage_runtime_info.json`.

## Implicit cofactor-four projected base

For this exact curve model, `y² + xy = x³ + 1`, the projected x coordinate
of a point with raw x coordinate `x` satisfies

`x([4]P) · (x¹² + x⁴) = x¹⁶ + x⁸ + 1`.

[`chain_s3_projected_sparse.py`](chain_s3_projected_sparse.py) restricts raw
`x` to normal-basis weight at most four, requires `x · z = 1` and
`Tr(x + z) = 0` for a rational curve lift, then constrains the projected
subgroup x by this equation. The test suite checks every nonzero x at n=5
and n=11 against exact group multiplication, and the n=5 SAT control
checks every nonzero x. The n=131 controls receive independent Sage replay.
This Q1317 stage represents the **same n=83 factor-base policy, exact base
digest, and ordinary public target** as Q1316. Its raw leaf choices are
verified against the archived projected base after any SAT model.

| n=83 query | Formula vars / CNF / XOR / AND | Unassisted result | Charged target-PDP wall | Post-run control |
| --- | --- | --- | ---: | --- |
| Planted | 121,746 / 354,114 / 2,909 / 116,947 | 120 s cap; no model | 120.05 s | SAT; raw, projected, and public points replayed |
| Ordinary | 121,746 / 354,114 / 2,909 / 116,947 | 1,000,002 conflicts; no model | 109.61 s | no witness available |

The exact-base-orbit formula on this same target has 872,878 CNF clauses
and 48,466 AND gates. The implicit variant has fewer clauses and more field
multiplication gates. The ordinary n=83 run still yields no natural relation;
the planted control is a correctness check, not a relation-yield measurement.
The source-bound receipts, logs, gzip XCNFs, and checked Sage runtime are
archived under `runs/n83_*_projected_sparse.*` and
`projected_sparse_sage_runtime_info.json`.

The planted n=83 witness was also used for **oracle-assisted localization**.
All four raw leaf x values were pinned, leaving projected x and both S3
intermediates free; the formula reached 200,002 conflicts in 15.24 s without
a model. Pinning all four projected leaf x values as well still reached
200,001 conflicts in 21.74 s without a model. Pinning the first S3
intermediate x in addition returned a verified public relation after 56,002
reported conflicts and 5.31 s; pinning both intermediates returned the same
relation in 3.42 s. These four single-run controls use known witness
coordinates, have `workload_id: null`, and say nothing about natural
relation yield. They identify the free first S3 root as a useful target for
a deterministic field-root circuit or propagator; they are not a lower bound
on other solvers.

[`s3_root_oracle.py`](s3_root_oracle.py) now computes both exact roots of
`S3(a,b,c)` as a quadratic in `c`, using an odd-degree half trace for
distinct nonzero `a,b`. Exhaustive n=5 and sampled n=11 group-sum tests,
plus the known n=53 and n=83 relation chains, check those roots.
[`chain_s3_rooted.py`](chain_s3_rooted.py) encodes each early root with one
branch bit in place of a free n-bit intermediate. Q1319 is the n=83 stage
proposal for this method; it uses the same exact projected W≤4 base and
public target as Q1317 and keeps `candidate_id: null`.

| Rooted n=83 diagnostic | Formula vars / CNF / XOR / AND | Unassisted result | Charged PDP wall | Locked full-size control |
| --- | --- | --- | ---: | --- |
| Planted, first root encoded, four raw leaves pinned | 135,940 / 395,864 / 3,242 / 130,725 | 200,001 conflicts; no model | 17.75 s | SAT; public relation replayed |
| Planted, first two roots encoded, four raw leaves pinned | 150,134 / 437,282 / 3,575 / 144,503 | 200,002 conflicts; no model | 20.06 s | SAT; public relation replayed |
| Ordinary, first two roots encoded, no pins | 150,134 / 436,950 / 3,575 / 144,503 | 1,000,002 conflicts; no model | 90.68 s | no witness available |

The rooted formulas are mathematically consistent on the pinned controls,
but the Boolean search still did not recover a relation at these caps.
The pinned rows are oracle-assisted diagnostics, with `workload_id: null`;
the ordinary row retains the frozen n=83 workload ID. Conflict counts are
solver-specific Boolean events, not field-operation equivalents. Encoding
one or two roots does not yet give a measured n=131 solve cost.

## Full group-addition circuit

[`chain_group_add.py`](chain_group_add.py) encodes the complete affine point
sum, including each leaf's y coordinate and the public target's x and y.
The three addition slopes use a forward exponentiation circuit for field
inversion, so the intermediate points are determined when the leaves are
fixed. Every link requires distinct input x coordinates. This excludes
doubling and cancellation cases; the known n=53 and planted n=83 witnesses
are nondegenerate. Q1320 uses the exact archived n=53 subgroup-orbit selector.
Q1321 uses Q1317's exact implicit cofactor-four projected W≤4 n=83 base.
Both are stage proposals, with `candidate_id: null` and `isogeny: "none"`.

| Stage query | Exact base B / folded columns | Formula vars / CNF / XOR / AND | Unassisted result | Charged target-PDP wall | Leaf-fixed control |
| --- | ---: | --- | --- | ---: | --- |
| Q1320 n=53 ordinary, known satisfiable | 24,062 / 227 | 76,437 / 226,920 / 3,062 / 71,126 | 120 s external cap; no model | 120.02 s | SAT and public-sum replay in 0.29 s solver wall |
| Q1321 n=83 planted, known satisfiable | 1,934,066 / 11,651 | 262,182 / 764,884 / 6,395 / 253,814 | 120 s external cap; no model | 120.02 s | SAT and public-sum replay in 3.40 s solver wall |
| Q1321 n=83 ordinary | 1,934,066 / 11,651 | 262,182 / 764,884 / 6,395 / 253,814 | 120 s external cap; no model | 120.03 s | no witness available |

The controls pin the four known leaf points but leave both intermediate sums
and all slopes free. They validate full-size arithmetic propagation; their
times are excluded from the unassisted stage costs. A first n=83 planted
attempt lost its timing receipt when the filesystem filled while writing the
locked-control formula. Its primary formula and solver log are preserved as
an `artifact_write_failure` row with a null timing; the clean planted run above
was repeated afterward. All complete rows preserve the checked Sage runtime,
source and solver hashes, solver logs, and compressed formulas. No unassisted
query returned a verified relation, so these censored attempts do not yield a
success-cost estimate or a degree-131 \(2^x\) projection.

## Reverse-link group propagation

[`chain_group_add_reverse.py`](chain_group_add_reverse.py) adds the redundant
equation \(P_4=T-P_{123}\) to the exact four-point circuit. It computes the
right side through another forward field-inversion circuit. Q1322 is the
n=53 exact-base stage; Q1323 is the n=83 implicit projected-base stage.
The extra affine link requires \(x(T)\ne x(P_{123})\), so these variants cover
a narrower nondegenerate subset. Both known full-size witnesses satisfy that
restriction. Pinned diagnostics set `workload_id: null`; the unpinned ordinary
rows retain their frozen one-target workload IDs.

| Reverse-link query | Unassisted or oracle-pinned result | Charged PDP or diagnostic wall | Verified relation |
| --- | --- | ---: | --- |
| Q1322 n=53 ordinary, first 3 leaves pinned | SAT | 0.57 s diagnostic | known public relation; fourth leaf recovered |
| Q1322 n=53 ordinary, first 2 leaves pinned | 20 s cap | 20.01 s diagnostic | none |
| Q1322 n=53 ordinary, no pins | 60 s cap | 60.01 s target PDP | none |
| Q1323 n=83 planted, first 3 leaves pinned | 30 s cap | 30.01 s diagnostic | none |
| Q1323 n=83 ordinary, no pins | 60 s cap | 60.04 s target PDP | none |

The n=53 three-pin result is a concrete propagation improvement: the same
known witness with three leaves pinned timed out after 20 seconds before the
reverse equation was added. The n=83 full formula accepts its witness when
all four raw and projected leaves are fixed, and exact group replay passes.
Its three-pin timeout is therefore a censored search on a satisfiable
instance, consistent with a remaining sparse-raw-x preimage/base-selection
bottleneck. No unassisted query succeeded. The formulas, logs, checked Sage
runtime, and source hashes are retained for all five rows; the full-size
locked n=83 control is in the circuit test suite.

At n=131, Q1318 uses the proposed W≤6 projected base and the same
cofactor-four identity. [`screen_n131_projected_sparse.py`](screen_n131_projected_sparse.py)
assembled a formula with **300,098 variables, 881,690 CNF clauses, 4,589
XOR rows, and 291,475 AND gates**; 40 seeded sparse rational x values
passed both producer group controls and an independent checked-Sage replay
of the two lifts, fourfold projection, and subgroup membership. No solver
was invoked. Conditional on Q1303's
sample-based **25.13 million** folded-column estimate, the four one-hot
exact-base selectors alone would emit about **2.647 billion CNF clauses**
(sampling-only 95% normal interval 2.632–2.662 billion), roughly 3,000
times this implicit formula's clause count. This is a formula-size
comparison, not a solver-work ratio or a complete-solve projection. This
Q1318 screen predates the exact Q1413 base enumeration below. Its
sample-based selector count remains a historical conditional calculation;
both Q1303 and Q1318 still have `candidate_id: null` because the complete IC
pipeline is not specified or measured.

## Matched pair-table stage

[`matched_n53_pair_table.py`](matched_n53_pair_table.py) reuses the prior
signed-Frobenius pair search on **the exact same n=53 base and public target**.
It recomputes the full base's canonical x-orbit digest and confirms the
24,062-point, 227-column set matches the compressed archive. It found one
verified four-point relation after 500,000 table samples and 171,218 query
samples: \(671{,}218=2^{19.356}\) logical pair samples. In the source-bound
run, its base enumeration took 32.78 s; table construction took 41.69 s;
target-query sampling took 22.34 s. The relation is checked to sum to the
public target. It does not
recover the target scalar, determine base logs, or measure matrix rank.

[`matched_n83_pair_sample.py`](matched_n83_pair_sample.py) samples the exact
n=83 base and ordinary public target with a lazy, cached reconstruction of
orbit points. In the source-bound run, its 20,000 table samples took 6.48 s
and 20,000 query samples took 5.83 s. It saw no quotient-key hit, as expected at this small sample
size. These times include lazy representative lifting in the table phase.
They are a throughput diagnostic, not a complete pair-table search or a
relation-yield estimate.

## N83 target coverage and exact weight-five follow-up

[`screen_n83_four_point_support.py`](screen_n83_four_point_support.py)
audits the exact subgroup-base sizes before interpreting the n=83 timeouts.
For a uniformly selected nonidentity target and **any fixed base** of size
\(B\), there are at most \(\binom{B+3}{4}\) four-point multisets, each
summing to at most one target. Thus the target's chance of having any
four-leaf representation is at most
\(\binom{B+3}{4}/(r-1)\), without an independence assumption. For Q1302's
exact n=83 weight-four base (\(B=1{,}934{,}066\), \(K=11{,}651\)), the bound is
**0.24113**. At least **75.887%** of uniform nonidentity targets have no
four-leaf representation in that base. The \(\binom{B}{4}/r=0.2411\)
distinct-subset mean is also an exact average over uniform subgroup targets;
only converting that mean to a 21.4% coverage probability uses a Poisson
model. This bound does not prove whether the one frozen Q1302 target is
representable.

Q1324 changes the factor base while keeping curve
`EC1N83Ckb1h876c2921cb64`, the same ordinary public point and workload
`bab50a1e5f66`, the one-thread solver, and a 120-second target-PDP cap. Its
Q1041 selected weight-five base is already frozen in the repository with
**B=4,000,102**, **K=24,097**, and point-set digest
`e6ea595bbd32b3f2a17a0a913962cc961b3acdc7ff70d8859fb74f1ad20f2c62`.
The exact base construction uses 24,097 distinct projected signed-Frobenius
orbits from a seeded stream of five-bit normal-x supports. The Q1324 input
manifest retains that construction, the original point-key digest, and a
separate derived representative-x digest. It remains a `Q` proposal with
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`.
The checked-Sage [full base replay](runs/n83_q1324_q1041_full_base_verification.json)
verified all 24,097 projected representatives on the exact curve and in the
declared subgroup, and checked their signed-Frobenius orbit keys.

| Q1324 stage | Formula variables / CNF / XOR | Result | Charged stage wall | Verified relation |
| --- | ---: | --- | ---: | --- |
| Four leaves and both middle x values locked | 148,839 / 1,732,068 / 1,635 | SAT | 3.91 s oracle control | yes, planted |
| Ordinary public target, no locks | 148,839 / 1,731,814 / 1,635 | 120-second timeout | 120.02 s target PDP | none |

The locked result independently replays the four subgroup points and their
signed sum. It checks that the larger exact base is present in the encoding;
it is not ordinary yield. For this base the exact average distinct-subset
count is **4.412** per uniform target. A Poisson model gives 98.8% coverage,
but the bound cannot establish coverage of the particular frozen target.
The ordinary run has no model, field-operation count, rank row, or DLP. Its
wall times are exploratory stage diagnostics on a host without a CPU
isolation receipt, so no CPU speedup ratio is claimed. The checked Sage
runtime, compressed XCNFs, solver logs, source hashes, and independent
artifact audit are retained.

## Complete N83 weight-five base and Q1325 stage

[`enumerate_n83_weight5_full.py`](enumerate_n83_weight5_full.py) enumerates
every nonzero normal-basis x mask of weight at most five using one necklace
per Frobenius orbit. It found **373,101** raw x orbits and **186,612**
rational, nonidentity signed-Frobenius point orbits after cofactor-four
projection. There were no duplicate projected orbits. The exact subgroup
base has **B=30,977,592** usable points before folding and **K=186,612**
columns. Its sorted full-point-key digest is
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The field degree is the odd prime 83, and this curve has only four points
over F₂, so no nonidentity point in the odd-order subgroup is Frobenius
fixed. Each such point has 83 distinct Frobenius images, none equal to its
negative; each stored column therefore represents 166 points.
All Q1324 selected-base columns and all Q1302 weight-four columns are
subsets. The [independent replay](runs/n83_q1325_full_base_replay.json)
checked every stored representative on the curve and against its canonical
key, sampled subgroup membership, and reconstructed both subset bases.
Base enumeration took 66.25 seconds and peaked at 85,835,776 bytes RSS on
this unisolated host; this target-independent preparation is outside the
one-target online interval.

Q1325 keeps exact curve `EC1N83Ckb1h876c2921cb64`, ordinary workload
`bab50a1e5f66`, public target, and one-thread CryptoMiniSat setting. Its
implicit cofactor-projected sparse-leaf encoding has four leaves and three
compact S3 links; it does not expand S5. The [protocol](q1325_protocol.json)
retains `candidate_id: null`, `run_id: null`, and `isogeny: "none"` because
the rest of the IC pipeline is incomplete.

| Q1325 stage | Formula variables / CNF / XOR | Result | Charged stage wall | Verified relation |
| --- | ---: | --- | ---: | --- |
| Planted, all leaves and middle x values locked | 122,074 / 355,596 / 2,909 | SAT | 2.07 s oracle control | yes, planted |
| Ordinary public target, no locks | 122,074 / 354,766 / 2,909 | 120-second timeout | 120.01 s target PDP | none |

The planted witness independently replays as four subgroup points summing
to its target. It is an encoding check, not a natural relation. For this
base, \(\binom{B}{4}/r=15{,}869.003\) is the **exact mean** number of
distinct four-point subsets over uniformly chosen subgroup targets. It
does not prove that this particular target has a representation; a Poisson
coverage conversion would add an independence assumption. The ordinary
receipt contains no model, relation, field-operation count, or rank row.
All wall times here are exploratory diagnostics without a host isolation
receipt. The solver logs, compressed formulas, source digests, and checked
Sage runtime are retained with the receipts in `runs/`.

## Work accounting and decision

[`work_ledger.json`](work_ledger.json) separates the measured pair counts
from the unknown complete cost. Under a simple independent, uniform
pair-sum-orbit model, a balanced random quotient pair table at n=131 would
need roughly \(2^{61.48}\) *logical pair samples* for one expected match.
This is a heuristic for the sampled pair-table method, not a measured lower
bound, a field-operation conversion, or a projection for the SAT solver.
It already excludes base construction, final LA, and target recovery.

[`screen_n131_weight6_pair_index.py`](screen_n131_weight6_pair_index.py)
applies the separate pure pair-index rank-collection law to Q1303's proposed
W≤6 base estimate. With conditional \(B\approx6.584\) billion and
\(K\approx25.13\) million, building all \(nK^2\) quotient pair states is
about \(2^{56.20}\) states. Storing just one 17-byte 131-bit key per state
would take about \(2^{60.29}\) bytes, before witnesses or table overhead.
Under uniform pair keys and the optimistic assumption that each match adds
one rank row, collecting \(K\) rows costs about \(2^{89.35}\) logical pair
probes. Propagating only the sample's conditional 95% \(B\) interval gives
\(2^{89.34}\)–\(2^{89.36}\) probes. This screen is 28.35 bits above a
\(2^{61}\) *pair-action* budget before final LA and target recovery. It rules
out that pure indexed-pair family under its stated model; it is neither a
lower bound on other decomposition algorithms nor a complete field-operation
projection. This historical sample-based screen is superseded for base
geometry by the exact Q1413 enumeration below; Q1416 recomputes the same
pair-action model against that exact base.

For n=83, the exact counting bound above shows why Q1302's weight-four
ordinary timeout is ambiguous. Q1324's selected base and Q1325's complete
weight-five base raise the four-subset mean, but both timed out without a
natural relation. These are censored solver attempts on one frozen target,
not measured zero relation rates for a complete collector.

For the proposed n=131 W≤6 base, [`estimate_n131_weight6_base.py`](estimate_n131_weight6_base.py)
enumerates every weight-one and weight-two x support and draws distinct,
seeded supports at weights three through six. On 208,646 checked supports it
estimates **6.584 billion** cofactor-projected usable points, conditional on
the two lifts remaining distinct and cofactor projection being injective on
the full sparse set. The normal-approximation 95% interval from sampling is
**6.545–6.622 billion** under those conditions, giving about **25.13 million**
signed-Frobenius columns. The weight-at-most-two sub-base is exact in this
representation: **B=8,384**, **K=32**. The higher-weight base has not been
enumerated **in this sampling receipt**. Q1413 below supplies the exact
base count and digest separately. Q1303 retains `candidate_id: null` because
the full IC pipeline is not specified or measured.
This projected-raw-x W≤2 control is a different factor-base policy from the
separate N131 base that selects subgroup points whose **projected point's** x
has weight exactly two (`B=3,668`, `K=14`); the latter also has a different
exact curve ID. Their `fb` counts must not be interchanged.

An independent checked-Sage replay verifies the type-II normal-basis
generator polynomial, all 131 gamma squaring images, sampled rationality
classifications, and the exhaustive weight-one/two rationality counts. It
also checks 16 distinct weight-two projected control points and subgroup
membership on bounded controls. The exact W≤2 projected B=8,384 is a
producer enumeration; Sage has not exhaustively replayed every projected
point. Both source-bound receipts are in `runs/` and use
`n131_sample_sage_runtime_info.json`. The derived uniform-subset screen
assumes every four-point subset sum is independently uniform and every hit
adds one rank. Even if **all** base construction, final matrix, descent,
replay, and conversion work cost zero, it leaves an optimistic ceiling near
\(2^{33.2}\) field-operation equivalents per ordinary query under a
\(2^{61}\) total cap. This is a design budget from explicit assumptions,
not a measured solver cost or a complete-solve projection.

The complete n=131 work exponent remains **unknown**. The corrected,
exact-base, selected and complete n=83 weight-five, and implicit projected-base
SAT stages are censored. The native root search below verifies one n=53
ordinary relation and an independent row, but its n=83 run is capped without
a relation. Natural useful-row yield at n=83, final matrix solving, target
descent, and independent scalar replay are absent. There is therefore no
defensible complete-solve upper projection below \(2^{61}\), and the
degree-131 challenge gate remains closed. Existing complete ECDLP claims
cannot be inferred from a relation stage or a planted witness.

Q1325's exact n=83 four-subset mean is about 15,869. Q1303's conditional
n=131 W≤6 estimate gives only about **0.115** under its stated geometry
assumptions. The n=83 timeout therefore cannot be fitted directly as an
n=131 per-decomposition cost or success rate. It isolates a leaf-choice
search problem on a comparatively dense base; it does not establish an
n=131 stage exponent.

## Nested exact N53 base search and Q1326 diagnostic

Q1326 freezes a seed-ordered, nested search over Q1301's **same exact n=53
parent base and public target**. The parent remains B=24,062/K=227, curve
`EC1N53Ckb1hf77aab617904`, and ordinary workload `74f2979b3e68`.
Each attempt permits an exact subset of parent signed-Frobenius orbits; its
actual eligible B, K, orbit-key digest, seed, and cap are in the
[Q1326 protocol](q1326_protocol.json). Subsets restrict the solver's leaf
choices and do not redefine a successful point as outside the parent base.

| Attempt | Eligible B / K | Exact uniform-target four-subset mean, rounded | Ordinary result | Charged target PDP |
| --- | ---: | ---: | --- | ---: |
| 64 columns | 6,784 / 64 | 4.19 | 30 s timeout, no model | 30.02 s |
| 96 columns | 10,176 / 96 | 21.22 | 1,000,001 conflicts, no model | 18.81 s |
| 128 columns | 13,568 / 128 | 67.07 | 1,000,001 conflicts, no model | 18.82 s |

The three attempts charged **67.65 seconds** in total to that one target.
Their exact subset means are averages over uniform subgroup targets; none
proves that this target has a relation inside one of the restrictions. A
post-run [pair-table support diagnostic](runs/n53_q1326_k128_support_diagnostic.json)
used 500,000 table and 1,500,000 query samples on the 128-column subset
without a match. That bounded search does not prove absence and is not
credited to the compact-S3 solver.

The 64-column subset also has a **known-satisfiable planted target** built
from four of its points. Locking the leaves and intermediate x coordinates
returned and independently replayed a relation in **0.054 s**. On that
same target, the [unpinned formula](runs/n53_q1326_planted_unpinned.json)
reached **1,000,002 conflicts** in **22.97 s** without a model. This is a
direct solver-search diagnostic on a restricted satisfiable instance, not
an ordinary relation-yield estimate. It shows that shrinking the leaf list
alone did not make this chained-S3 encoding recover a witness at the tested
cap. Timings are exploratory because the host has no CPU isolation receipt.
The source-bound XCNFs, logs, checked Sage runtime, and independent replay
are retained with the seven Q1326 receipts.

## Exact native arithmetic bridge

The [N53](field_bridges/n53_onb_poly.json) and
[N83](field_bridges/n83_onb_poly.json) bridge records map the frozen type-II
normal-basis coordinates into polynomial bit coordinates. The respective
internal moduli are \(z^{53}+z^6+z^2+z+1\) and
\(z^{83}+z^7+z^4+z^2+1\). The canonical instance still uses the original
normal-basis field record and the same EC1 curve ID; the polynomial encoding
is an implementation detail for native field and root arithmetic. It is not
an isogeny (`isogeny: "none"`). A separately catalogued polynomial-basis
curve would need its own curve ID under the naming protocol.

The checked-Sage derivation verifies 128 random multiply, square, and inverse
controls and nine group-addition controls at each degree. An independent
bit-polynomial [replay](verify_onb_poly_bridge.py) checks every basis-pair
product (2,809 at N53 and 6,889 at N83), both conversion directions, the
public targets, and all archived base representatives (227 at N53 and
186,612 in the complete Q1325 N83 base). The source-bound
[N53](runs/n53_onb_poly_bridge_replay.json) and
[N83](runs/n83_onb_poly_bridge_replay.json) receipts both pass; the
[runtime record](bridge_sage_runtime_info.json) was saved before the jobs.
The artifact audit now validates 129 receipts including the native stages,
single-target adaptive-window probes, and fused-root diagnostics.

The bridge itself is a field-conversion control. A full pair-root index scales
roughly as \(K^2n\) states: about 2.7 million for Q1301's 227 columns at
N53, but about 2.9 trillion for Q1325's 186,612 columns at N83. The N83
solver therefore uses a bounded search. Its cap covers only a small part of
that state space.

## Q1327/Q1328 bounded native S3 root search

The [stage protocol](q1327_q1328_native_root_protocol.json) gives the native
`PDP4root` solver its own proposal IDs. Q1327 reuses Q1301's exact N53 base;
Q1328 reuses Q1325's exact N83 base. Both retain their original EC1 curve
IDs, public targets, workload IDs, and `isogeny: "none"`. Their
`candidate_id` and `run_id` remain `null` because the full IC pipeline is
not specified or measured. The [exporter](export_native_root_inputs.py)
converts the exact archived orbit representatives through the verified
field bridge; the [native source](native_s3_root.rs) indexes S3 roots in an
open-addressing table and tests one target-seeded Frobenius orientation per
state on ordinary workloads. All four signs are tested on a table hit.

| Proposal | Exact base B / K | Indexed pair states | Target states scanned | Target PDP and native check | Peak RSS | Ordinary result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q1327 N53 | 24,062 / 227 | 2,731,037 (complete) | 49,228 | 0.106 s | 285 MB | one relation, independently verified |
| Q1328 N83 | 30,977,592 / 186,612 | 2,000,000 (capped) | 2,000,000 | 9.355 s | 755 MB | no relation under this cap |

Index preparation was target independent and took 2.779 s at N53 and
4.849 s at N83, including the N83 representative-shift table. The native
[N53](runs/n53_native_root_full.json) and
[N83](runs/n83_native_root_capped_2m.json) receipts retain separate setup,
index, and target-dependent operation counts. N53's target work includes
**98,455 S3 calls, 787,654 top-level field multiplications, 98,462
top-level inversions**, all failed probes before the match, and the native
four-point check. The N83 target spent **4,000,000 S3 calls, 32,000,000
top-level multiplications, and 4,000,000 top-level inversions**. These
counts are not yet calibrated into one field-operation-equivalent unit; the
reported wall times are exploratory because this host lacks an isolation
receipt. Neither row is a single-target IC or rho speedup measurement.

Independent checked-Sage [N53 replay](runs/n53_native_root_independent_replay.json)
checks every leaf against the exact signed-Frobenius base and subgroup,
re-adds the four points to the frozen public target, derives the quotient
relation row, and finds rank **2** for that row paired with the existing
matched pair-table row. The [N83 replay](runs/n83_native_root_independent_replay.json)
checks a native generator-plus-target S3 control and the source-bound cap;
it records the no-hit result as censored. It does not prove that the public
target lacks a four-point representation. The N83 cap is only
\(2{,}000{,}000/(186{,}612^2\cdot83)\approx6.92\times10^{-7}\) of the
full quotient pair-state count.

This no-hit row is specific to Q1328's Q1325 base and frozen target. The
separate [Q1091 quotient-pair campaign](../koblitz-pair-claw-20260929/README.md)
recovered an N83 relation and scalar on a different exact factor base and
workload. Its measured yield and work do not transfer to Q1328.

### Q1329 N83 unpinned four-leaf correctness control

The [Q1329 fixture](runs/n83_q1329_planted_fixture.json) plants one target
from two states in the same 2,000,000-state Q1328 sampled index. The
[control manifest](native_inputs/n83_planted_control_manifest.json) passes
the public target and frozen base metadata to the native solver; it contains
no leaf coordinates or index positions. This is a separate one-target
planted workload
`c530b6f0b4dd`, using the same curve ID, exact Q1325 base
\(B=30{,}977{,}592\), and \(K=186{,}612\). It keeps `candidate_id` and
`run_id` null and `isogeny: "none"`.

The [native run](runs/n83_q1329_planted_unpinned.json) indexed 2,000,000
states, then found a four-point relation after one target state and 34 of
83 Frobenius orientations. Target-dependent native work counted 67 S3 calls,
550 top-level multiplications, 74 inversions, and 0.000178 s. Target-
independent setup plus index construction took 5.033 s and peak RSS was
691 MB. The [independent checked-Sage replay](runs/n83_q1329_planted_independent_replay.json)
verifies all four recovered subgroup points against the exact archived base
and independently adds them to the target. The four points occupy distinct
signed-Frobenius columns. This is an unpinned search correctness result, not
an ordinary-query yield measurement or a complete DLP solve. Q1329 tries all
83 orientations per state, while the ordinary Q1328 run tries one; its time
cannot be used as a paired ordinary speed comparison.

### Q1330/Q1331 single-target S3 inversion-window comparison

Every Q1327–Q1332 workload here contains exactly one frozen public target.
The `s3_batch_size=4096` field in the newer records is an internal inversion
window over S3 root equations while building the reusable pair index and
scanning that one target. It never groups targets, shares work across target
points, or measures target-batch throughput. The historical filenames and
proposal IDs retain “batch” for artifact continuity; their workload is still
one target. Q1327/Q1328 use the same evaluator with a one-state window, while
Q1330/Q1331 use a 4,096-state window. The [protocol](q1330_q1331_batch_root_protocol.json)
freezes the same curves, bases, public targets, workload IDs, state order,
and caps. A native exhaustive test matched the windowed and direct roots
for all 1,024 input pairs over \(\mathbf F_{2^5}\) at window sizes 1, 2, 7,
128, and 1,024.

| One-target ordinary stage | Inversion window | Target mul / inv calls | Target states scanned / prepared | Target-dependent PDP and relation check | Exploratory stage ratio vs window 1 | Peak RSS | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Q1327 N53 | 1 | 787,654 / 98,462 | 49,228 / 49,228 | 105.81 ms | 1.00x | 285 MB | one relation, verified |
| Q1330 N53 | 4,096 | 1,171,431 / 20 | 49,228 / 53,248 | 51.57 ms | 2.05x | 288 MB | same relation |
| Q1328 N83 | 1 | 32,000,000 / 4,000,000 | 2,000,000 / 2,000,000 | 9,355.02 ms | 1.00x | 755 MB | no relation under cap |
| Q1331 N83 | 4,096 | 43,998,533 / 489 | 2,000,000 / 2,000,000 | 3,250.87 ms | 2.88x | 759 MB | same censored no-hit result |

These are target-stage observations for one point, after the target-independent
pair index is ready. The target clock covers PDP scanning and the native
relation check; it excludes process launch and index construction. The ratios
are exploratory only: the host has no isolation receipt, and no complete
target DLP or paired rho solve was measured. They are not single-target
end-to-end speedup claims. The one-target [N53 replay](runs/n53_batch_root_independent_replay.json)
checks the same four subgroup/base points and rank-two pairing with the
matched pair-table row. The one-target [N83 replay](runs/n83_batch_root_independent_replay.json)
checks the same exact-base, source-bound cap and retains its censored result.
The window trades extra multiplications for fewer inversions. At N53 the
match occurs inside a window, so 53,248 states are prepared even though only
49,228 are inspected before the relation.

The [source-level arithmetic expansion](runs/n53_n83_s3_primitive_field_calls.json)
charges the multiplications and squarings *inside* each field inversion in
the pinned `crypto` implementation. Its nonzero Itoh–Tsujii chain uses
`bit_length(n-1)+popcount(n-1)-2` multiplication calls and `n-1` squaring
calls per inverse. The native source guards every inversion input against
zero. These are exact counts of calls to the pinned field methods, including
failed target probes; they are not CPU instructions or a weighted field-
operation equivalent.

| Stage | Index primitive mul / sqr calls | One-target primitive mul / sqr calls |
| --- | ---: | ---: |
| Q1327 N53 direct | 40,964,193 / 142,013,924 | 1,476,888 / 5,120,035 |
| Q1330 N53 window 4,096 | 30,042,713 / 34,684 | 1,171,571 / 1,051 |
| Q1328 N83 direct | 32,000,000 / 164,000,000 | 64,000,000 / 328,000,000 |
| Q1331 N83 window 4,096 | 22,002,445 / 40,098 | 44,002,445 / 40,098 |

Basis conversions, canonical rotations, hash probes, memory traffic, and
other work remain separate. The exact call vector improves stage accounting;
it does not supply natural relation yield or the complete \(2^x\) cost.
Regenerate it with
`python3 experiments/compact-s3-m4-20261003/derive_s3_primitive_calls.py --check`.

The separate [Q1332 planted one-target control](runs/n83_q1332_batch_planted_unpinned.json)
uses Q1329's single planted target, the exact Q1325 base, all 83 orientations,
and a 4,096-state inversion window. Its [independent replay](runs/n83_q1332_batch_planted_independent_replay.json)
checks all four subgroup/base points and their sum. The planted relation is
found at state one after 34 orientations, but the fixed window prepares
4,096 states and 339,968 orientations. Its 140.09 ms target stage versus
0.178 ms for the window-1 planted control exposes a severe early-hit penalty.
Q1332 is a correctness control, not a natural-yield estimate; this one-target
result motivates an adaptive per-target window schedule.

### Q1333–Q1335 adaptive windows for one target

The [adaptive protocol](q1333_q1334_adaptive_window_protocol.json) keeps one
frozen target in every run and grows the target-query inversion window through
`[1, 16, 64, 256, 1024, 4096]` states. The reusable pair index still uses a
4,096-state arithmetic window. This schedule changes how root equations for
one target are grouped; it never processes multiple target points together.
Q1333 and Q1334 use the exact Q1330/Q1331 ordinary points, bases, state order,
and caps. Q1335 replays Q1329's single planted target as an early-hit control.

| Run | Target count | Scanned / prepared target states | Target PDP and relation check | Exploratory ratio vs window 1 | Exploratory ratio vs fixed 4,096 window | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q1333 N53 ordinary | 1 | 49,228 / 50,513 | 50.60 ms | 2.09x | 1.02x | same verified relation as Q1330 |
| Q1334 N83 ordinary | 1 | 2,000,000 / 2,000,000 | 3,261.38 ms | 2.87x | 1.00x | no relation at cap |
| Q1335 N83 planted control | 1 | 1 / 1; 34 / 83 orientations tested / prepared | 0.102 ms | 1.75x | 1,376x | same verified planted relation |

The ordinary rows remain target-stage diagnostics, not recovered DLPs. The
N53 and N83 ratios are exploratory single-run wall-time ratios on an
unisolated host, not CPU speedup claims. Q1335 is a synthetic correctness
control and cannot estimate natural relation yield. It shows the early-hit
cost change clearly: the fixed window prepared 4,096 target states and
339,968 orientations for this state-one hit; the schedule prepared one state
and 83 orientations. The adaptive build and all three run manifests record
`target_count: 1`; the independent Sage replays check the N53 ordinary and
N83 planted relations against the frozen target and exact factor base.
None of these stages includes a complete relation matrix, target descent,
recovered scalar, or paired rho measurement, so the ECC2K-130 single-target
end-to-end speedup remains unknown.

### Q1336–Q1338 fused regular-root formula

The [Q1336/Q1337 protocol](q1336_q1337_fast_root_protocol.json) keeps the same
one-target workloads and adaptive target-local window schedule, but rewrites
the regular S3 root calculation from
`d = (c*a) * (a/(a*ps))` to `d = c*a^2/(a*ps)`. The denominator inverse is
already shared, so the fused form saves exactly one field multiplication per
regular S3 root. The native exhaustive test again matches the independent
direct-root implementation for all 1,024 input pairs in \(\mathbf F_{2^5}\).

| Proposal | Target count | S3 roots | Field multiplications, adaptive → fused | Target PDP / relation-check time, adaptive → fused | Adaptive / fused stage-time ratio | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Q1336 N53 ordinary | 1 | 101,026 | 1,111,249 → 1,010,223 | 50.60 → 51.66 ms | 0.979x | same independently verified relation; slower in this observation |
| Q1337 N83 ordinary | 1 | 4,000,000 | 43,998,521 → 39,998,521 | 3,261.38 → 3,253.02 ms | 1.003x | both capped without a relation |
| Q1338 N83 planted control | 1 | 166 | 1,837 → 1,671 | 0.102 → 0.105 ms | 0.974x | same independently verified planted relation |

The stage ratio is adaptive elapsed time divided by fused elapsed time, so
values above one favor the fused formula. These are single
observations on an unisolated host: the small N83 difference is not a
repeatable speedup, and N53 plus the early-hit planted control are slower.
This kernel change is a no-go for a wall-time claim despite its exact
operation-count reduction. The [ordinary replays](runs/n53_fast_root_independent_replay.json)
and [planted replay](runs/n83_q1338_fast_planted_independent_replay.json) are
source-bound checked-Sage records; the N53 relation matches and the N83
ordinary result remains censored. The fused variant still reports only a
bounded point-decomposition stage: no complete DLP, final relation-matrix
solve, target descent, or paired single-target rho solve was measured.

Conditionally applying Q1303's estimated N131 W≤6 column count to this
**full-index design** gives about \(2^{56.20}\) pair states before target
queries. Applying the observed nondegenerate kernel's eight multiplication
calls and one inversion call per state gives about \(2^{59.20}\) top-level
multiplications plus \(2^{56.20}\) top-level inversions for index construction
alone. Under the separately measured 4,096-state inversion window and the
same all-regular root assumption, the conditional index calls become
\(2^{59.66}\)
multiplications plus \(2^{44.20}\) inversions. One complete target scan would
add \(2^{60.66}\) multiplications; index plus that scan would call for
\(2^{61.24}\) multiplications before relation collection or matrix work.
This is a conditional full-scan scenario, not a lower bound on earlier hits
or other solver families. None of these counts is a calibrated
operation-equivalent or complete \(2^x\) solve projection. The actual N131
base count and digest in this historical screen were sample estimates; the
exact Q1413 enumeration below supersedes them for base geometry.

### Fixed-state target-coverage bound for Q1331

The [exact counting screen](runs/n83_q1331_uniform_target_coverage_bound.json)
puts the two-million-state N83 cap in context without assuming random root
keys. Each indexed pair state names two exact-base x coordinates. Their signs
give at most four subgroup pair sums; all 83 global Frobenius rotations give
at most \(4n\) pair-sum points per state. Let \(U\) be their union over the
fixed \(M\) index states. A four-leaf relation found by this design must
write the target as a sum of two points in \(U\). Because the group is
abelian, at most \(|U|(|U|+1)/2\) distinct targets can have that form.
The frozen state order is target independent, so a uniformly drawn
nonidentity subgroup target has the rigorous coverage upper bound

\[
\Pr[Q\in U+U]\leq
\min\!\left(1,\frac{(4nM)(4nM+1)}{2(r-1)}\right).
\]

For Q1331, \(n=83\), \(r=2{,}417{,}851{,}639{,}230{,}796{,}216{,}685{,}689\),
and \(M=2{,}000{,}000\), yielding **at most \(9.118\times10^{-8}\)** of
uniform nonidentity targets. Even the *upper bound* cannot reach 50% until
\(M\geq4{,}683{,}567{,}037\) states, 2,342 times the measured cap. This
counts all 83 orientations and assumes a perfect collision check, so better
inversion scheduling alone does not change it. It is a support bound for a
fixed, target-independent pair-state set, not an estimate of the hit rate on
the one frozen target or a bound on target-adaptive or algebraic solvers.
The screen is regenerated with
`python3 experiments/compact-s3-m4-20261003/screen_q1331_target_coverage.py --check`.

### Q1400 matched Q1325 quotient-pair comparator

Q1400 is a separate `PDP4mitm` stage proposal on the **same exact**
`EC1N83Ckb1h876c2921cb64` curve, Q1325 base
(\(B=30{,}977{,}592\), \(K=186{,}612\), the same set digest), and ordinary
public target as Q1331. Its [input exporter](export_q1400_pair_inputs.py)
losslessly pads each 21-byte canonical point key into the 32-byte native
record consumed by the [frozen group-law engine](native_q1400_pair_comparator.cpp).
The [protocol](q1400_pair_protocol.json) fixes two million table descriptors
and 16,384 query representatives, which expand to 2,719,744 signed target-
side pair checks. The method and memory cap differ from Q1331, so its wall
times are stage diagnostics, not a controlled solver speed comparison.

The [ordinary run](runs/n83_q1400_pair_comparator.json) found **zero exact
hits**. It recorded 258 Bloom positives, all rejected by exact replay.
Target-dependent query plus exact replay took 0.634 s; target-independent
native table construction took 0.407 s, native base loading 0.272 s, and
peak RSS was 1,246,986,240 bytes. The checked-launcher base export cost was
separately recorded, including startup. CPU wall times are exploratory on
this unisolated ARM64 host. The run has no field-operation-equivalent count,
verified relation, useful-row yield estimate, or complete DLP result.

The separate [Q1401 planted control](runs/n83_q1401_pair_planted_native.json)
passes only its public target and the same Q1325 base to the native engine.
It returned one exact hit. [Independent checked-Sage replay](runs/n83_q1401_pair_planted_independent_replay.json)
reconstructed all four subgroup/base points from the reported table/query
positions, checked four distinct signed-Frobenius columns, and re-added them
to the public target. The witness metadata stayed in the verifier's
[fixture](runs/n83_q1401_pair_planted_fixture.json), outside the native
input. This is a correctness control, not ordinary relation-yield evidence.

For this *fixed* Q1400 rectangle, the table side contains at most \(2nM\)
group pair points after sign and Frobenius folding, and the query side at
most \(2nR\), where \(M=2{,}000{,}000\) table descriptors and
\(R=16{,}384\) query representatives. Thus its support over a uniformly
drawn nonidentity subgroup target is at most
\((2nM)(2nR)/(r-1)=3.735\times10^{-10}\). This exact counting bound
explains why the ordinary no-hit under this small cap is not a natural-yield
measurement. It does not apply to a larger or target-adaptive rectangle.

### Q1402 fixed-pair family counting screen

The [Q1402 screen](runs/n83_n131_q1402_fixed_pair_family_screen.json)
extends the Q1400 counting argument to any **fixed, target-independent**
signed-Frobenius table of \(M\) full-point pair descriptors and fixed query
schedule of \(R\) descriptors. Each side contributes at most \(2n\)
signed/Frobenius group points per descriptor. Hence a uniformly drawn
nonidentity subgroup target has support probability at most
\(\min(1,4n^2MR/(r-1))\), without assuming that pair sums are random.
An S3 state that emits both relative signs counts as two full-point
descriptors in this screen.
At Q1400's measured \(M=2{,}000{,}000\), even the ceiling cannot reach 1%
at N83 until \(R\geq438{,}716{,}003{,}635\) representatives; for 50%, it
requires \(R\geq21{,}935{,}800{,}181{,}729\). Q1400 used 16,384.

For Q1303's **sampled** N131 weight-at-most-six base estimate, the screen
grants the fixed table every ordered orbit pair and both relative signs,
\(M=\lceil2nK^2\rceil\), or about \(2^{57.20}\) descriptors. Even then,
1% uniform-target support requires at least \(5.993\times10^{14}\)
(\(2^{49.09}\)) fixed query representatives, and 50% requires
\(2.996\times10^{16}\) (\(2^{54.73}\)). Granting \(2^{31}\) query
representatives leaves a support ceiling of \(3.5833\times10^{-8}\).
The upper end of the sampled 95% base-size interval changes that ceiling
to only \(3.6257\times10^{-8}\); the interval is statistical, not a hard
bound on the actual N131 base. Descriptors are not calibrated field
operations, so this is a conditional family screen and not a complete
\(2^x\) work projection. Target-adaptive schedules, guided query laws, and
algebraic solvers lie outside its scope.

### Q1400 primitive field-call accounting

The [source-bound call expansion](runs/n83_q1400_primitive_field_calls.json)
counts Q1400's recorded no-hit path through the pinned N83 native source.
Table construction used 10,003,912 field multiplication calls and 2,040,098
squaring calls, including its batch inversions. The target-dependent pair
query, signed complement, exact replay, and Frobenius setup together used
16,901,576 multiplications and 4,944,328 squarings. The replay includes the
second full table pass triggered by 258 Bloom positives. Base-orbit
expansion separately used 30,977,592 squarings before the target.

The recorded 0.634 s times target query and exact replay, but omits the
166 target-dependent Frobenius setup squarings before the native query timer.
It is therefore a **partial stage wall interval**, not a complete target
online wall time. Native controls, conversion, canonicalization, hashing,
memory traffic, and calibration into a common weighted operation unit remain
separate. Q1331's matched-target vector has 44,002,445 multiplications and
40,098 squarings for its different two-million-state S3 search; neither
vector gives cost per useful row because both N83 runs found none.

### Q1403 ordered implicit Q1325 S3 stage

Q1403 tests one specific symmetry reduction in the compact SAT formula:
sort the four **raw normal-basis x masks** before applying Q1325's exact
cofactor-four projection and three-link S3 chain. The original Q1325
source remains unchanged. Q1403 uses the same exact N83 curve, full
weight-at-most-five base (\(B=30{,}977{,}592\), \(K=186{,}612\), the same
set digest), and ordinary public-target workload `bab50a1e5f66`.
Its [frozen protocol](q1403_ordered_q1325_protocol.json) keeps
`candidate_id: null` and `isogeny: "none"`.
The [named PDP-stage comparison](runs/n83_q1325_q1403_named_stage_comparison.json)
assigns `PS1N83Ckb1fb30977592PDP4sathfa12f6d598da` to the existing
Q1325 ordinary receipt and `PS1N83Ckb1fb30977592PDP4sath59cbea1842cc`
to Q1403. Their stage run IDs append `Wbab50a1e5f66R1`. These `PS1`
labels identify exact-base decomposition profiles, not complete `IC1`
candidates; the original `Q` receipts retain their names.

| Q1403 query | Formula vars / CNF / XOR / AND | Result | Charged PDP wall | Verified relation |
| --- | --- | --- | ---: | --- |
| N83 planted, fully locked | 123,310 / 358,560 / 3,158 / 117,934 | SAT, 56,001 reported conflicts | 2.411 s control | one, independently replayed |
| N83 planted, unpinned | 123,310 / 357,730 / 3,158 / 117,934 | 60 s external cap, no model | 60.010 s control | none |
| N83 ordinary | 123,310 / 357,730 / 3,158 / 117,934 | 120 s external cap, no model | 120.013 s target PDP | none |

The ordinary Q1325 formula without raw-leaf ordering had 122,074 variables,
354,766 CNF clauses, 2,909 XOR rows, and 116,947 AND gates; it also
reached the 120 s cap without a model. Q1403's ordinary child-process peak
RSS was 695,042,048 bytes, with 128,843,776 bytes for the parent process.
These exploratory wall measurements on an unisolated host are not a
controlled speed comparison. The [independent checked-Sage replay](runs/n83_q1403_ordered_control_replay.json)
reconstructed the four subgroup points from the sorted raw masks, checked
their exact base membership, applied the solver-reported signs, and re-added
them to the planted public target. Its planted relation is a correctness
control, not a natural-yield sample.

Ordering preserves the nondegenerate four-point group relations represented
by this chain because group addition is commutative and the S3 intermediates
can be rebuilt in sorted order. The
ordinary no-model result remains censored; the unpinned planted timeout
shows that this encoding still has a search bottleneck on a satisfiable
N83 instance at the frozen cap. No ordinary useful row, natural yield,
field-operation conversion, or complete \(2^x\) solve cost follows.

### Q1404 raw-preimage W≤5 S3 stage

Q1404 keeps the **same** exact Q1325 N83 base, curve, and ordinary public
target, but applies the compact S3 chain to four sparse **raw** x masks.
It computes all four `[4]` preimages of the public target and selects one
inside the SAT formula. This removes the four nonlinear cofactor-projection
circuits from Q1325's implicit formula; each SAT relation is projected and
checked against Q1325's exact point-key set afterward. The ordinary
preimage computation is charged to that target. The construction is the
weight-five counterpart of the earlier weight-four Q1307 raw-preimage
encoding. See the [frozen protocol](q1404_raw_preimage_w5_protocol.json).

| Q1404 N83 query | Formula vars / CNF / XOR / AND | Result | Charged stage wall | Verified relation |
| --- | --- | --- | ---: | --- |
| Planted, fully locked | 65,221 / 190,428 / 1,245 / 62,001 | SAT | 0.173 s control | one, independently replayed |
| Planted, unpinned | 65,221 / 189,928 / 1,245 / 62,001 | 60 s external cap, no model | 60.009 s control | none |
| Ordinary | 65,221 / 189,928 / 1,245 / 62,001 | 1,000,001 conflicts, no model | 90.930 s target stage | none |

For the ordinary target, 0.006 s was charged to public-point validation
and complete preimage construction, and 90.924 s to exact input checks,
formula construction, writing, and the SAT attempt. The ordinary
child-process peak RSS was
802,373,632 bytes; the parent peak was 95,715,328 bytes. These are
exploratory wall measurements on an unisolated host. CryptoMiniSat's
conflicts and propagations are solver-specific diagnostics, not calibrated
field operations. The [independent checked-Sage replay](runs/n83_q1404_raw_control_replay.json)
reconstructed all four target preimages from their x coordinates, checked
the raw and projected sums, and verified four distinct Q1325 columns for
the locked planted relation.

The [named PDP-stage comparison](runs/n83_q1325_q1404_named_stage_comparison.json)
retains Q1325's `PS1N83Ckb1fb30977592PDP4sathfa12f6d598da` and gives
Q1404 `PS1N83Ckb1fb30977592PDP4satha37fe097800f`; each ordinary run ID
appends `Wbab50a1e5f66R1`. Both keep `candidate_id: null` and
`isogeny: "none"`. The raw-preimage formula has roughly half as many
variables and AND gates as Q1325's implicit formula, but neither found an
ordinary model within its frozen cap. The unpinned planted timeout shows
that removing the projection circuits alone did not clear the N83 search
bottleneck. No natural yield, cost per useful row, or complete solve
exponent can be estimated from these censored runs.

### Q1408 balanced W≤5 S3 tree

Q1408 keeps Q1404's exact `EC1N83Ckb1h876c2921cb64` curve, Q1325
factor base (B = 30,977,592; K = 186,612), complete raw target-preimage
selector, ordinary workload `bab50a1e5f66`, solver, and limits. It changes
the three S3 links from a left-associated chain to the balanced tree
`S3(x1,x2,u), S3(x3,x4,v), S3(u,v,target)`. See the
[frozen protocol](q1408_balanced_s3_w5_protocol.json) and
[named stage comparison](runs/n83_q1404_q1408_named_stage_comparison.json).

| Q1408 N83 query | Charged stage wall (exploratory) | Solver result | Verified relation |
| --- | ---: | --- | ---: |
| Planted, leaves and pair sums locked | 0.173 s | SAT | 1 control |
| Same planted target, unpinned | 60.010 s | external timeout | 0 |
| Matched ordinary target | 90.501 s | 1,000,001 conflicts, censored | 0 |

The ordinary and unpinned formulas each have 65,221 variables, 189,928 CNF
clauses, 1,245 XOR rows, and 62,001 AND gates, equal to Q1404's shape. The
[independent checked-Sage replay](runs/n83_q1408_balanced_control_replay.json)
verified the locked witness, both raw pair sums, the public-point sum, and
four distinct exact Q1325 columns. Neither unpinned search returned a model.
The two ordinary no-hit rows are censored stage measurements. Q1408's stage
ID is `PS1N83Ckb1fb30977592PDP4sath0c555b4e4d40`; its ordinary run ID
adds `Wbab50a1e5f66R1`. `candidate_id` remains null. CPU wall ratios on
this unisolated host are exploratory, and a complete solve exponent remains
unknown.

### Q1406 uniform-query relation-supply bound for Q1303

The [Q1406 counting screen](runs/n131_q1406_uniform_query_bound.json)
adds a necessary budget for **the proposed N131 W≤6, m=4 base** without a
Poisson or independent-subset-sum assumption. With `B` distinct usable
base points, there are at most \(\binom{B+3}{4}\) unordered four-point
multisets, including repeated points. Their sums distribute over the
subgroup of order `r`. A uniform nonidentity query therefore has at most
\(\binom{B+3}{4}/(r-1)\) expected decompositions, regardless of how those
sums are distributed. This also bounds its probability of having any
decomposition. Every decomposition can add at most one relation row.

Conditionally rounding Q1303's sampled base estimate to full 262-point
signed-Frobenius orbits gives `B=6,583,581,064` and
`K=25,128,172`. The uniform-query representation mean and coverage
ceiling are **0.1150186**. For a collector that obtains all `K` required
independent rows from uniform nonidentity four-summand queries, Markov's
inequality requires at least **207,546,988 queries** for a 95% chance of
rank `K`, even if it returns every representation and every row is novel.
The condition that expected rank reaches `K` requires at least
**218,470,513 queries**. Correlation between queries does not weaken these
bounds when each query has the declared uniform marginal.

Dividing an abstract `2^61` total-work cap by the 95%-rank necessary
query count leaves at most **`2^33.37`** work units per query when all
other costs are set to zero; the expected-rank version gives
`2^33.30`. Across Q1303's conditional normal-approximation 95% base
interval, the 95%-rank ceiling varies from `2^33.35` to `2^33.40`.
These are affordability ceilings, **not** measured solver costs or a
complete `2^x` projection. The actual N131 base count and digest are
unknown, the statistical interval is not a hard bound, and a nonuniform
guided query law or an external source of factor-base rank rows lies outside
this screen. Recompute it with
`python3 experiments/compact-s3-m4-20261003/screen_q1406_uniform_query_bound.py --check`.

### Q1407 compact S3 formula-size control

The [Q1407 source-bound screen](runs/n53_n83_n131_q1407_compact_formula_shape.json)
rebuilds the raw-preimage compact S3 formula and matches the earlier
ordinary N53 and N83 formula counts exactly. Those real-target controls use
the frozen Q1301 W≤3 and Q1325 W≤5 bases and all their respective raw
cofactor preimages. The N131 row uses four distinct **placeholder** x values
to fix the selector shape; it is not a curve target or a solver run.

| Formula shape | Variables | CNF clauses | XOR rows | AND gates | Total literal occurrences |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 W≤3, 428 actual raw preimages | 26,922 | 100,060 | 795 | 25,281 | 459,580 |
| N83 W≤5, four actual raw preimages | 65,221 | 189,928 | 1,245 | 62,001 | 569,288 |
| N131 W≤6, four placeholder x values | 160,061 | 470,612 | 1,965 | 154,449 | 1,410,528 |

The N131 row is about `2^20.43` emitted literal occurrences and never
materializes expanded S5. Thus the earlier expanded-S5 construction cost
does not apply to this compact encoding. The row measures formula **shape**,
not SAT search work, successful decomposition cost, exact N131 base
membership, or a complete solve. Recompute it with
`python3 experiments/compact-s3-m4-20261003/screen_q1407_compact_formula_shape.py --check`.

### Q1405 compact five-summand planning screen

The [source-bound Q1405 screen](runs/n83_n131_q1405_m5_chain_screen.json)
tests whether **one more short S3 link** is a better next solver target. A
five-leaf chain uses four S3 links and three free intermediate x coordinates;
it need not expand or materialize S6. Q1405 uses the exact Q1302 N83
weight-at-most-four base, not Q1325's weight-five base. Thus the N83 m4/m5
comparison changes both arity and factor-base policy and compares two full
PDP designs rather than SAT speed alone. Both use curve
`EC1N83Ckb1h876c2921cb64`, ordinary workload `bab50a1e5f66`, and
`isogeny: "none"`. Q1405 is a `PDP5sat` **proposal**, with
`candidate_id: null` and no measured solver run.

| Exact N83 base and method | B before folding | Folded K | Mean distinct subsets per uniform target |
| --- | ---: | ---: | ---: |
| Q1302 W≤4, m=5 | 1,934,066 | 11,651 | 93,270 |
| Q1325 W≤5, m=4 | 30,977,592 | 186,612 | 15,869 |

| Conditional N131 design | Sampled B | Estimated folded K | Mean distinct subsets per uniform target | Optimistic queries for K novel rows | Zero-other-cost per-query ceiling under 2^61 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q1405 W≤5, m=5 | 308.7 million | 1.178 million | 34.31 | 2^20.17 | 2^40.83 |
| Q1303 W≤6, m=4 | 6.584 billion | 25.13 million | 0.115 | 2^27.79 | 2^33.21 |

For N131, the W≤5 row reuses **only strata one through five** of Q1303's
weight-stratified rationality sample, whose bounded controls passed an
independent checked-Sage replay. Its conditional
normal-approximation 95% B interval is 306.1–311.3 million. The exact W≤5
point set, its digest, and its folded column count have **not** been
enumerated. The subset mean is a uniform-target average conditional on B;
the queries and ceiling additionally assume a Poisson hit law, one novel
rank row per hit, and zero base construction, matrix, descent, replay,
conversion, and failed-attempt overhead. They are planning screens, not a
measured relation yield or a complete work exponent. Q1303's conditional
numbers use the same assumptions for comparison.

The compact Q1405 formula shape on the **actual N83 ordinary raw target
preimages** has 86,386 variables, 252,012 CNF clauses, 1,660 XOR rows, and
82,668 shared AND gates. A formula-shape construction at N131 W≤5 using
four distinct placeholder x values has 212,460 variables, 625,451 CNF
clauses, 2,620 XOR rows, and 205,932 AND gates. The N131 placeholders are
not curve preimages, no SAT solve was attempted, and formula construction
does not establish solve cost. Reproduce the screen with
`python3 experiments/compact-s3-m4-20261003/screen_q1405_m5_chain.py --check`.

### Q1410 paired N53 balanced-S3 stage

Q1410 uses the same balanced S3 builder and one-million-conflict ordinary
limit as Q1408. Its exact N53 input is Q1301's
`EC1N53Ckb1hf77aab617904` curve and W≤3 factor base: B = 24,062 actual
usable points, K = 227 signed-Frobenius columns, and a complete 428-point
raw target-preimage coset. The ordinary public target has workload ID
`74f2979b3e68`. The [protocol](q1410_balanced_s3_n53_protocol.json) pins
the source hashes and separates its locked control from the ordinary run.

The first verifier preflight, Q1409, returned a SAT model but rejected it
because it compared Q1325-style packed full-point keys with Q1301's
canonical **x-coordinate** keys. Its [failure receipt](runs/n53_q1409_planted_locked_verification_failure.json)
retains the source, protocol, solver log, and formula archive; it counts as
no verified relation. Q1410 corrects that key check. Its locked control
uses the existing, independently checked relation on the **same ordinary
N53 public target**, with four distinct Q1301 columns. The
[independent replay](runs/n53_q1410_balanced_control_replay.json) verifies
both signed pair sums, the public-point sum, the exact base membership, and
the four distinct columns.

| Balanced-S3 stage | Charged target-stage wall (exploratory) | Solver result | Ordinary relation |
| --- | ---: | --- | ---: |
| Q1410 N53 locked witness | 0.269 s | SAT, independently verified control | control only |
| Q1410 N53 ordinary | 69.581 s | 1,000,002 conflicts, censored | 0 |
| Q1408 N83 ordinary | 90.501 s | 1,000,001 conflicts, censored | 0 |

The [named cross-degree stage record](runs/n53_q1410_n83_q1408_balanced_stage_comparison.json)
assigns Q1410 `PS1N53Ckb1fb24062PDP4sath3630c237df8c`, with run ID
suffix `W74f2979b3e68R1`. The curves and bases differ, and both ordinary
runs stop at a conflict cap without a model. Their wall ratio therefore
does not measure solve growth, natural relation yield, or cost per useful
row. Q1327/Q1330's native N53 root method found an ordinary relation on
this exact base; Q1410's censored SAT row illustrates its search limit at
the frozen cap. The complete N131 work exponent stays unknown.

### Q1412 ordered balanced-S3 N53 method gate

Q1412 keeps Q1410's exact Q1301 curve, base, ordinary target, complete
428-preimage selector, solver, and one-million-conflict cap. It adds unsigned
`x1 <= x2 <= x3 <= x4` constraints to remove leaf permutation symmetry.
The [protocol](q1412_ordered_balanced_n53_protocol.json) pins the formula
and runner sources. The locked control sorts the known ordinary relation's
four raw x coordinates and recomputes both balanced pair sums. Its
[independent replay](runs/n53_q1412_ordered_control_replay.json) verifies
the public sum and four distinct exact Q1301 columns.

| Q1412 N53 query | Charged stage wall (exploratory) | Solver result | Ordinary relation |
| --- | ---: | --- | ---: |
| Sorted known witness locked | 0.274 s | SAT, verified control | control only |
| Same ordinary public target, unpinned | 95.875 s | 1,000,001 conflicts, censored | 0 |

The [named matched stage comparison](runs/n53_q1410_q1412_named_stage_comparison.json)
assigns Q1412 `PS1N53Ckb1fb24062PDP4sath25a3d6a29f3e`. Both Q1410 and
Q1412 fail to return a model at the frozen conflict cap; their unisolated
wall times do not measure a solve speed ratio. The locked control establishes
that ordering retained a known relation. The N53 method gate failed, so
Q1412 does not advance to an N83 run or a degree-131 work projection.


### Q1413 exact projected-x base enumeration

For this characteristic-two curve, rationality of a nonzero raw x is
equivalent to `Tr(x + x^-1) = 0`, and `x([2]P) = x(P)^2 + x(P)^(-2)`.
Applying that doubling identity twice computes the x-coordinate of the
cofactor-four projection without lifting both signed points for every raw
support. The [Q1413 source](enumerate_q1413_projected_x.py) enumerates one
normal-basis necklace per Frobenius orbit, checks rationality, discards
identity projections, and deduplicates the projected x orbits. Its
[protocol](q1413_projected_x_protocol.json) binds the exact curve, source,
reference bases, and checked Sage runtime. The digest encoding is **sorted
canonical cyclic-Frobenius x keys**; it differs from Q1302's ONB-coordinate
x-key encoding and Q1325's full-point-key encoding.

| Exact enumeration | Actual usable points B | Folded columns K | Control |
| --- | ---: | ---: | --- |
| [N83 W≤4](runs/n83_q1413_projected_x_w4.json) | 1,934,066 | 11,651 | Same orbit set as Q1302 |
| [N83 W≤5](runs/n83_q1413_projected_x_w5.json) | 30,977,592 | 186,612 | Same orbit set as Q1325 |
| [N131 W≤5 prefix](runs/n131_q1413_projected_x_w5.json) | 309,633,434 | 1,181,807 | Exact subset of proposed Q1303 W≤6 base |
| [N131 W≤6 full](runs/n131_q1413_projected_x_w6.json) | 6,559,634,788 | 25,036,774 | Exact Q1303 projected base; digest `e5f66c394406…` |

The n=83 checks compare the **entire** computed orbit sets with the
separately archived Q1302 and Q1325 sets, beyond matching counts. The
[independent Sage replay](runs/n131_q1413_sage_projection_replay.json)
checks rationality on 80 fresh n=131 sparse x supports and compares every
rational support's projection with Sage's fourfold group multiplication,
including 16 subgroup-order checks. These controls
validate the projection formula and the declared encoding; they are not
ordinary decomposition attempts or relation-yield measurements. The full
W≤6 run examined 50,071,373 raw x-orbits and retained 25,036,774 distinct
projected subgroup x-orbits. Its 5,667-second L0 enumeration interval stops
before sorting and digesting the final key set, so it is not complete base
construction cost. The [API-call vector](runs/q1413_exact_base_api_call_vectors.json)
records 75,108,147 direct field-inverse calls, 100,142,746 traces, and
3,254,780,620 canonical-rotation steps for this run; it omits internal
arithmetic, hashing, sorting and conversion costs. No common work unit or
complete solve exponent follows from this base receipt.
The n=131 W≤6 digest has one complete enumeration pass. The frozen-artifact
verifier checks its source/protocol hashes, weight-five prefix, and accounting;
the n=83 controls compare complete sets, while the independent Sage replay
checks sampled n=131 points. These checks do not constitute a second full
n=131 enumeration. The protocol and receipts are first published together,
so this is a reproducible computational geometry result rather than a
precommitted selection experiment.

### Q1414 and Q1416 exact-base work screens

The [Q1414 uniform-query bound](runs/n131_q1414_exact_uniform_query_bound.json)
uses the exact W≤6 base and all unordered four-point multisets, including
repeated points. Their count divided by the nonidentity subgroup target
count is at most **0.11335429** representations per uniformly distributed
query. If all 25,036,774 rank rows must come from such queries, every
representation is returned, and every row is optimistically novel, Markov's
inequality still requires at least **209,828,278 queries** for a 95% chance
of full rank. Under an abstract `2^61` total-work target with all other
costs set to zero, this leaves less than `2^33.36` work units per query.
This is a necessary affordability ceiling for the stated uniform marginal,
not a measured solver cost or a bound on guided nonuniform collectors.

The [Q1416 pure quotient-pair-index model](runs/n131_q1416_exact_base_pair_index_screen.json)
builds `nK² = 82,116,046,854,846,956` raw pair states (`2^56.19`).
Materializing one 17-byte key for each state alone would occupy
1,395,972,796,532,398,252 bytes (`2^60.28`), before witnesses or index
overhead. Under its stated uniform pair-key and one-novel-row-per-match
model, the index plus K rows needs about `2^89.36` logical pair actions,
`2^28.36` above the abstract `2^61` target. The storage figure applies to
this uncompressed materialization, and the action count is a model, not a
lower bound on other PDP families or a calibrated complete-solve estimate.

### Q1415 N53 XOR Gaussian solver method gate

The [Q1415 protocol](q1415_gauss_n53_protocol.json) reruns the exact Q1410
ordinary N53 XCNF on the same curve, 24,062-point base, target, and formula
with CryptoMiniSat's `maxmatrixcols=10000` and `autodisablegauss=0`.
Q1410's default 1,000-column limit discarded its 212-by-8,586 XOR matrix;
the [Q1415 log](runs/n53_q1415_gauss_ordinary.stdout.txt) confirms that
three such matrices were active. The [frozen run](runs/n53_q1415_gauss_ordinary.json)
still reached the external 120-second cap without a SAT model or verified
relation. Its conflict count is unreported because the process timed out
before final solver statistics. The [named stage comparison](runs/n53_q1410_q1415_named_stage_comparison.json)
uses distinct canonical `PS1` stage IDs and keeps both failures. It records
the older stage IDs as aliases: those archived IDs hashed run limits and a
target-specific formula. The canonical stage hash includes the exact curve,
field, base, formula method, source components, solver binary, and algorithmic
XOR-Gauss flags; it leaves caps, thread count, and target formula in the run
record. The timing intervals differ, and the host is unisolated, so they
provide no controlled wall-time speed ratio. This flag change did not pass
the N53 ordinary method gate;
there is no Q1415 N83 solver result or solve-growth estimate.
The Q1415 protocol and result are first published together. This bounded
negative run is exploratory; it was not a precommitted statistical selection
test.

### Q1419 N53/N83 balanced-S3 partial-pinning controls

The [pre-registered Q1419 protocol](q1419_partial_pin/protocol.json) and
[16-cell archive verification](q1419_partial_pin/verification.json) test the
same balanced-S3 encoding on exact Q1301 N53 and Q1325 N83 bases. All cells
are known satisfiable controls; none measures ordinary relation yield. Both
fully locked cells return and verify the archived relation. Releasing only
the two pair-intermediate x coordinates reaches one million conflicts at
both degrees (15.382 and 19.653 exploratory solver seconds). Every N83
cell beyond full lock is censored under the 60-second/one-million-conflict
caps. N53 `free_target` returns the same archived witness leaves in 3.528
seconds, so difficulty is not monotone in the number of free variables.
The [cell table and next gate](q1419_partial_pin/README.md) preserve every
failure, formula, log, named `PS1` stage and source hash. The complete
degree-131 work exponent remains unknown.

### Q1420 N53/N83 external exact-S3 root propagation

The [pre-registered Q1420 protocol](q1420_root_theory/protocol.json) replaces
both pair-intermediate S3 Boolean circuits with exact external field-root
clauses. Its [six-cell archive](q1420_root_theory/verification.json) verifies
the known-witness `full_lock` and `free_mids` controls at both N53 and N83.
Those four SAT cells reuse two archived relations. The two unpinned ordinary
targets each reach the external 60-second cap with no model or verified
relation. The N53 ordinary solver's peak child RSS was 1.445 GB and the N83
ordinary solver's was 166 MB on this unisolated Darwin host. Their callback
operation counts are unknown because the external timeout kills the process
before it prints them. The [Q1420 result table](q1420_root_theory/README.md)
and ledger preserve the full per-cell costs and raw artifacts. This method
passes the fixed-leaf mechanism check but does not establish ordinary N83
yield, a solve-growth fit, or a complete \(2^x\) cost.

### Q1421 work-counted root-theory decision-policy comparison

The [pre-registered Q1421 protocol](q1421_work_counted/protocol.json) reuses
the exact Q1420 CNFs and ordinary public targets under CaDiCaL default and
leaf-first decisions. Its [eight-cell archive](q1421_work_counted/verification.json)
verifies all four fixed-leaf controls. All four unpinned ordinary cells reach
the synchronous 60-second wall cap without a model. Unlike Q1420, every
capped solver returns conflicts, decisions, pair assignments, exact-root and
field-operation counts. N83 default reaches only 2 distinct pair assignments
in 365,794 conflicts; leaf-first reaches 5,167 in 21,900 conflicts, but no
ordinary relation. At N53, default reaches 31,532 pair assignments and
leaf-first 62, again without a relation. The [Q1421 result table](q1421_work_counted/README.md)
preserves all field calls, exploratory walls, and memory. Both ordinary
variants are censored; neither a solve-growth fit nor a complete degree-131
\(2^x\) follows.

### Q1422 exact rational-leaf gate

The [pre-registered Q1422 protocol](q1422_leaf_lift_gate/protocol.json)
adds the sound raw-x condition \(\operatorname{Tr}(x+x^{-1})=0\) to
Q1421's leaf-first external-root solver. Checked Sage and native code agree
on sampled sparse/full-range x values and all archived witness leaves at
both degrees. The [four-cell archive](q1422_leaf_lift_gate/verification.json)
verifies both known-witness controls. Its ordinary N53 and N83 cells reject
58 of 109 and 2,622 of 5,269 completed leaf values respectively, yet both
reach the 60-second wall cap without a model. N83 pair-root calls fall from
5,167 in matched Q1421 to 2,645, while conflicts remain about 22,000.
The [Q1422 result table](q1422_leaf_lift_gate/README.md) retains all field
calls, memory, and censored outcomes. Curve-lift feasibility alone does not
supply an ordinary relation or a complete degree-131 \(2^x\).

### Q1423 target-coupled final S3 roots

The [pre-registered Q1423 protocol](q1423_target_coupled/protocol.json)
adds sound exact roots for the last S3 link once the first pair
intermediate and the public target-preimage selector are assigned. Both
known-witness controls verify. The [four-cell archive](q1423_target_coupled/verification.json)
records no ordinary N53 or N83 relation at the 60-second caps. Pair-first
search makes 62,269 and 66,824 distinct pair assignments respectively,
but the target-coupled final-root rule activates only once per ordinary
query. The [Q1423 result table](q1423_target_coupled/README.md) retains
field operations, conflicts, exploratory walls, and memory. The new rule
is sound, but this search order reaches it too late to constrain the
ordinary queries. A complete degree-131 `2^x` remains unknown.

### Q1424 early-target decision orders

The [pre-registered Q1424 protocol](q1424_early_target/protocol.json)
compares two decision orders that choose the public target selector before
leaf-pair search. Its [eight-cell archive](q1424_early_target/verification.json)
verifies all four known-witness controls. All four ordinary N53/N83 cells
still hit the 60-second wall cap without a relation. The new per-pair
counters show `target_first` spends the cap on pair 1 (58,514 and 65,289
root calls), while `target_mid_first` spends it on pair 0 (225,790 and
135,141 root calls). The final target-coupled root rule activates once in
each ordinary cell. The [Q1424 result table](q1424_early_target/README.md)
retains field operations, memory, and every censored outcome. Moving SAT
decisions alone does not solve the pair-feasibility problem or support a
complete degree-131 `2^x`.
The ledger also verifies exact curve, base digest, and target agreement with
the prior pair-table stages: Q1301 found a relation on the N53 target, while
Q1400's fixed N83 rectangle had no hit. Their workloads and resource limits
differ, so neither gives a controlled wall-time speedup for Q1424.

### Q1425 exact reverse pair roots

The [pre-registered Q1425 protocol](q1425_reverse_pair/protocol.json) adds
exact symmetric `S3` partner roots once a pair intermediate and one leaf are
fixed. The [eight-cell archive](q1425_reverse_pair/verification.json)
verifies all four controls with the partner leaves freed. All four ordinary
N53/N83 cells still hit the 60-second cap without a relation. Complete pair
root evaluations fall to 0–21 per ordinary cell, but reverse-root calls rise
to 562,424–1,008,552, and every ordinary reverse candidate examined is
rejected by the sparse weight bound. The [Q1425 result table](q1425_reverse_pair/README.md)
summarizes the caps; the ledger and receipts retain exact operation counts,
memory, and paired Q1424 identities. The
degree-131 complete `2^x` remains unknown.

An [exact sparse-pair support screen](q1425_reverse_pair/pair_support_screen.json)
counts at most `2M²` possible pair-intermediate x coordinates for `M`
nonzero sparse x choices, because each ordered pair has at most two `S3`
roots. On the exact N131 W≤6 base, an independently uniform field
intermediate therefore needs at least `2^64.78` logical trials in
expectation to land in *any* sparse-pair support. This is a conditional
uniform-sampling lower bound, not a cost bound for target-guided
intermediates or a complete ECDLP projection.

### Q1426 symbolic second-pair equations

The [frozen Q1426 protocol](q1426_symbolic_pair/protocol.json) inserts all
factored binary equations for `S3(leaf2, leaf3, mid1)=0` into the SAT
formula before decisions. It retains Q1425's exact reverse-root propagator
and uses the same ordinary targets, exact bases, and 60-second caps. The
[four-cell archive](q1426_symbolic_pair/verification.json) verifies both
freed-partner controls, with one independently replayed relation each.
Neither ordinary N53 nor ordinary N83 found a relation before its cap.
The N53 ordinary cell made 1,080,547 reverse partner calls, and the N83
cell made 485,107; every reverse candidate was rejected by the sparse
weight rule. The [Q1426 result table](q1426_symbolic_pair/README.md) and
work ledger retain the raw field-operation and memory counts. The symbolic
equation alone did not change the decisive rejection pattern. These
censored cells leave the degree-131 complete `2^x` unknown.

### Q1427 interleaved target-conditioned partner bits

The [frozen Q1427 protocol](q1427_interleaved_pair/protocol.json) keeps
Q1426's exact symbolic and external root constraints but alternates bits
of the two second-pair leaves after the target and intermediates are
constrained. Its [four-cell verification](q1427_interleaved_pair/verification.json)
independently replays both freed-partner controls. Both ordinary N53/N83
cells still hit the 60-second cap without a relation. Within that cap,
reverse partner calls fell to 135,226 at N53 and 71,988 at N83, factors
of 7.99 and 6.74 fewer than Q1426. Every reverse candidate still failed
the sparse weight rule. The [Q1427 result table](q1427_interleaved_pair/README.md)
and work ledger retain exact field-operation and memory counts. This
decision-order improvement is a stage diagnostic; natural yield and the
complete degree-131 `2^x` remain unknown.

### Q1428 partial-pair bilinear-span screen

The [Q1428 protocol](q1428_bilinear_span/protocol.json) tests a sound
linear-span necessary condition derived from the exact fixed-intermediate
`S3(a,b,m)` equation. Its [result](q1428_bilinear_span/result.json) shows
rank deficiency and correct rejections on synthetic N53/N83 partial
leaves; exhaustive N3/N5 checks validate the algebra and soundness.
However, the frozen sampling law has already fixed each leaf's full
weight allowance when rank first drops. The cardinality constraints would
then fix the remaining bits, so this screen does **not** establish early
solver pruning. It is neither an ordinary-query measurement nor a
degree-131 work estimate. The next test must leave weight capacity and
compare its rejection benefit with exact completion enumeration.

### Q1429 unsaturated partial-pair screen

The [frozen Q1429 protocol](q1429_unsaturated_span/protocol.json) leaves
one or two one bits available on each partial leaf and compares Q1428's
sound span condition with exact sparse completion and reverse `S3` roots.
Its [268-sample result](q1429_unsaturated_span/result.json) includes the
exact N53/N83 fields and an N131 W≤6 structural screen tied to Q1413's
exact base identity. At N131 with 32 free bits and two remaining one bits,
all four synthetic samples were rejected by the span test; an exact
enumeration would have made 529 reverse-root calls per sample. The filter
tested 1,024 bilinear columns per sample, a different work unit. No exact
pair occurred in any uniform-intermediate sample. These are not ordinary
queries, and the next gate is whether target-conditioned solver trails
actually reach such unsaturated states. The degree-131 complete `2^x`
remains unknown.

### Q1430 actual target-conditioned partial-pair trail

The [frozen Q1430 protocol](q1430_partial_trail/protocol.json) adds
observation-only counters to Q1427 on its exact N53/N83 ordinary targets.
Both known-witness controls verify, and both ordinary cells still hit the
60-second cap without a relation. The actual search reached 207,522 N53 and
81,765 N83 notification events with both second-pair leaves partial, one or
two weight units available on each, and at most 14/20 free bits respectively.
These are event counts, not distinct-state counts. The first 16 saved
distinct states per ordinary cell were all rejected by the independently
replayed sound span test. The [result table](q1430_partial_trail/README.md)
and [post-run audit](q1430_partial_trail/audit_verification.json) retain
the exact identities and failure rows. A typo in the frozen verifier was
repaired only in a separate audit; the solver, protocol, and receipts remain
unchanged. Reachability and selected-state rejection do not show net solver
savings, natural relation yield, or a complete N131 `2^x`.

### Q1431 guarded partial-span propagator

The [frozen Q1431 protocol](q1431_guarded_span/protocol.json) adds a sound
span rejection clause guarded by every fixed bit of the second pair and its
fixed intermediate. Its [112-case native/Sage validation](q1431_guarded_span/span_validation.json)
matches the independent span oracle and retains verified witness completions.
The [four-cell verification](q1431_guarded_span/verification.json) replays
both known-witness controls and sampled ordinary rejections. Both ordinary
N53/N83 searches still cap at 60 seconds without a relation. The filter
uses 67,632,400 and 53,520,040 field multiplications at N53/N83 while
reducing reverse pair-1 calls to 12,020 and 19,354. Total field
multiplications rise to 68,182,727 and 54,467,127, compared with matched
Q1430's 4,764,022 and 3,676,888 within the same cap. The search paths
differ, so these are charged stage diagnostics, not a wall-time speedup or
a relation-cost measurement. The [result table](q1431_guarded_span/README.md)
and ledger retain failures, operation counts, and claim limits. Complete
N131 `2^x` remains unknown.

### Q1432 exact span-coefficient cache

The [frozen Q1432 protocol](q1432_coefficient_cache/protocol.json) keeps
Q1431's rejection and clause semantics while reusing pair-basis products,
intermediate-keyed bilinear columns, and lazily computed linear columns.
The [112-case native/Sage validation](q1432_coefficient_cache/cache_validation.json)
matches the independent oracle and retains verified witnesses. Both controls
verify; both ordinary N53/N83 searches still reach the 60-second cap without
a relation. Total field multiplications fall to 1,457,636/1,296,699,
including 905,700/349,603 filter multiplications and cache construction,
from Q1431's 68,182,727/54,467,127. Retained cache payload lower bounds
are 2.21/4.56 MB; the receipts also preserve peak RSS. The [result table](q1432_coefficient_cache/README.md)
and [archive verification](q1432_coefficient_cache/verification.json) retain
all four cells. These are different censored search prefixes on an unisolated
host; no cost per useful relation, natural yield, or complete N131 `2^x`
can be inferred.

### Q1433 longer cached-solver ordinary queries

The [frozen Q1433 protocol](q1433_long_cached/protocol.json) runs the exact
Q1432 binary and public targets under 300-second/five-million-conflict caps.
Both known-witness controls independently verify. Both ordinary N53/N83
targets again reach the wall cap with zero relations: N53 records 903,175
decisions and 4,753,049 field multiplications; N83 records 677,658
decisions and 4,490,849 multiplications. Peak RSS reaches 1.56/2.22 GB.
The [result table](q1433_long_cached/README.md) and [archive verification](q1433_long_cached/verification.json)
retain the censored rows and exact factor-base identities. They are lower
bounds for those attempts, not solved-query costs or a natural-yield sample.
The complete N131 `2^x` remains unknown.

### Q1434 exact sparse-tail membership

The [frozen Q1434 protocol](q1434_exact_tail/protocol.json) adds an exact
weight-one completion check after Q1432's cached span screen. The
[60-case native/Sage validation](q1434_exact_tail/tail_validation.json)
matches direct `S3` enumeration and preserves verified witnesses. Both
known-witness controls verify. On ordinary N53/N83 queries, the new check
rejects 42,903/3,180 span-accepted states with no actual completion, but
both queries still hit the 60-second cap without a relation. Total charged
field multiplications are 2,036,720/1,372,405 on these different censored
prefixes. The [result table](q1434_exact_tail/README.md) and
[archive verification](q1434_exact_tail/verification.json) retain all four
cells, exact factor-base identities, raw operation counts and memory. No
ordinary solved-query cost or complete N131 `2^x` follows.

### Q1435 bounded one/two-weight completion

The [frozen Q1435 protocol](q1435_bounded_tail/protocol.json) extends the
exact completion check to one or two remaining weight units per leaf, with
a 4,096-candidate-pair cap. The [103-case native/Sage validation](q1435_bounded_tail/tail_validation.json)
covers all four slack patterns and preserves verified witnesses. Both
known-witness controls verify. On ordinary N53/N83 queries, the gate checks
328,408/3,067 span-accepted states and rejects every checked completion
domain. It tests 110,100,907/1,405,528 candidate pairs and charges
354,587,110/4,152,415 expansion XORs in addition to field arithmetic.
Both queries again reach the 60-second cap with zero relations. The
[result table](q1435_bounded_tail/README.md) and [archive verification](q1435_bounded_tail/verification.json)
preserve skipped domains, raw work and memory. All N53 2/2 domains exceed
the cap. No ordinary solved-query cost or complete N131 `2^x` follows.

### Q1436 one-sided affine sparse-pair feasibility

The [frozen Q1436 protocol](q1436_affine_pair/protocol.json) solves the
second leaf's free bits as an exact GF(2) linear system for each allowed
completion of the first leaf, using the fixed target-linked intermediate.
It preserves consistent rank-deficient systems as unknown. The [49-case
native/Sage validation](q1436_affine_pair/affine_validation.json) retains
all nine known witnesses, and the [archive verifier](q1436_affine_pair/verification.json)
independently replays sampled ordinary zero claims. Both controls return
verified relations. Ordinary N53/N83 searches cap at 60 seconds with zero
relations, after soundly rejecting 395,906/75,525 partial domains with
18/24 free bits per leaf. They charge 1,335,395,670/571,525,667 affine
XORs and still complete only one first pair each. The first v1 control had
a malformed JSON report and is [archived separately](q1436_affine_pair/failed_v1/README.md);
the v2 protocol was frozen before these four runs. The [result table](q1436_affine_pair/README.md)
and ledger preserve operations, memory, failures, and claim limits. No
successful ordinary-query cost or complete N131 `2^x` follows.

### Q1437 N131 W≤7 frontier sample

The [frozen Q1437 screen](q1437_weight7_frontier/README.md) samples 100,000
distinct weight-seven Frobenius x-orbits on the exact N131 curve. It finds
50,213 rational orbits, all with nonidentity fourfold projection and no
projected-key collision *within the sample*. An independent Sage group-law
replay passes on 32 controls. Conditional on no unsampled or cross-weight
projection collisions, the W≤7 base would have about 118.64 billion usable
points and 452.81 million folded columns. Its average unordered distinct
four-point subsets per uniform target would be about 12,128, versus 0.11335
for the exact W≤6 base. The optimistic `4K²` sparse-matrix proxy is
`2^59.51` logical row actions, only 1.49 bits below `2^61` before
modular arithmetic, relation collection, decomposition, and descent.

This is a conditional geometry screen, not actual W≤7 `B` or `K`, a measured
ordinary-query yield, or a complete solve projection. The [ledger](work_ledger.json)
retains actual W≤7 counts and N131 `2^x` as null. A larger base may make
relations more plentiful, but the compact solver still needs a target-
conditioned pair witness method and calibrated complete-work accounting.

### Q1438 exact denser N53/N83 bases and solver panel

The [Q1438 frozen panel](q1438_dense_base/README.md) enumerates the exact
N53 W≤4 and N83 W≤6 projected bases and reruns Q1436's native compact-S3
solver on the archived targets with the same decision policy and caps.
N53 has `B=324,042`, `K=3,057`, digest `9e12afb51aaf…`; N83 has
`B=408,131,750`, `K=2,458,625`, digest `c1ee6d106493…`. The old sets
are checked as exact prefixes, and four old-weight control/ordinary formulas
match Q1426 byte for byte. Both known-witness controls independently verify.
Both unpinned ordinary queries reach the 60-second cap without a relation;
each completes only one first-pair root call. The N53 public point is known
representable even on its old subset, so that censored N53 outcome directly
shows the current search failing to find an existing decomposition within
the cap. N83's particular target representability remains unproved. The
base change increases the uniform-target four-subset counting mean by about
30,000-fold at both degrees, but gives no measured successful-query cost or
degree-131 complete-work exponent. The [ledger](work_ledger.json) retains
the failed attempts and null claim fields.

### Q1439 fixed-leaf three-summand reduction

The [frozen Q1439 experiment](q1439_fixed_leaf/README.md) fixes one usable
raw factor-base leaf independently of each ordinary public target, subtracts
it from every raw cofactor preimage, and searches the remaining three leaves
with two compact factored S3 links. The exact Q1438 N53 W≤4 and N83 W≤6
bases, their B/K counts and digests, and the archived public targets are
preserved. The selected ordinary anchors and all adjusted targets are bound
in the protocol before execution. Both planted controls return independently
replayed four-point relations. The unpinned ordinary N53 and N83 cells each
reach the 60-second external cap with zero relations. A small-field check
covers every triple for the selected anchors at N3/N5, with exceptional
identity states counted separately.

A fixed anchor can miss a four-point solution, so these censored ordinary
runs cannot separate coverage from solver cost. The known N53 four-point
relation does not establish that the independent Q1439 anchor belongs to a
relation. The results therefore leave ordinary useful-row yield, successful
three-leaf cost, and complete N131 `2^x` unknown. Q1440 checks the
witness-informed anchor diagnostic below.

### Q1440 witness-informed anchor, other three leaves free

The [Q1440 frozen gate](q1440_witness_anchor/README.md) uses Q1439's exact
bases and two-S3 formula with an anchor from a known relation. N53 uses the
archived ordinary public point but reveals its known first leaf; N83 uses an
archived planted point. The remaining three leaves are unpinned. At each
degree, one cell pins the archived adjusted-target selector and one leaves it
free. Q1439's verified control model satisfies all four Q1440 XCNFs and
replays to the public point, proving that every cell is satisfiable.

Neither N53 cell finds a relation before 1,000,001/1,000,002 conflicts;
N83's two cells reach their 60-second wall caps with no relation. This shows
that Q1439's ordinary failures cannot be attributed solely to choosing an
anchor with no representation: this particular three-leaf SAT search also
stalls when a witness exists. These are witness-informed diagnostics, not
natural-yield or successful-cost measurements. The complete N131 `2^x`
remains unknown. The next solver gate remains a target-conditioned method
that obtains witnesses for both sparse pairs before a full pair assignment.

### Q1441 N131 full-base-scan budget screen

The [Q1441 frozen screen](q1441_full_scan_budget/README.md) puts a declared
abstract work unit on a solver that traverses every usable factor-base point
for each relation query. On the exact W≤6 base, Q1414's uniform-marginal
95%-rank floor requires at least 209,828,278 queries. One full scan per
query already costs `2^60.256` actions at one action per point; two actions
per point exceed `2^61` before matrix, descent, or verification. On the
conditional Q1437 W≤7 base, a one-row-per-query solver needs at least
`ceil(K)` queries, and one full scan per query costs about `2^65.542`
actions at the sample center. The result holds across Q1437's conditional
Wilson endpoints under the same no-collision assumption.

This excludes those specified full-scan families in the named abstract unit;
it does not measure a decomposition, calibrate a field operation, or bound a
compressed or multirow solver. Q1441 leaves complete N131 `2^x` null and
strengthens the need for a target-conditioned witness method that avoids a
base traversal on every query.

### Q1442 conditional selected-W7 base-size screen

The [Q1442 frozen model](q1442_selected_base_screen/README.md) tests a
deterministically selectable *partial* W7 orbit family as a future N131 base
design. Under its unverified Poisson coverage, collision-free orbit, and
one-novel-row-per-covered-query assumptions, a selected base around 11.969
billion points and 45.683 million folded columns minimizes the model's
one-action full-scan total near `2^59.407`. Its all-other-costs-zero budget
allows only about 3.017 abstract actions per scanned point. The full W7
sample center requires `2^65.542` in the same optimistic model.

The selected base has **not** been enumerated: actual B, K, and its set
digest remain null. The model is neither measured ordinary yield nor a
field-operation or complete-solve projection. It narrows a possible future
base choice while the joint target-conditioned four-point solver remains the
decisive missing measurement.

### Q1443 residual-pair support bound

The [Q1443 exact-family screen](q1443_residual_pair_bound/README.md) corrects
the next-method requirement. At Q1442's conditional selected-W7 size, a
uniform N131 target's residual after a target-independent first pair lies in
the factor-base pair-sum support with probability at most `2^-63.043`. Even
with a free exact residual-pair oracle, 95% chance of one relation needs at
least `2^62.969` individually tested first pairs in the screen's abstract
trial unit. For the exact W≤6 base, the corresponding necessary count is
`2^64.704`. Under a one-row-per-trial policy, the 95%-rank trial bounds are
far higher. These statements apply to the declared uniform-target,
target-oblivious-first-pair family; they do not bound a joint target-guided
search or compressed batch-pair method.

Thus an isolated fixed-residual pair oracle can calibrate a kernel, but
cannot by itself provide a plausible complete `2^x` below `2^61`. The
next solver must couple both sparse pairs to the public target *before*
enumerating first-pair candidates. Q1443 still records no ordinary N83
relation, no complete-solve exponent, and no challenge permission.

### Q1444 sound WDSat adapter diagnostic

The [Q1444 adapter stage](q1444_wdsat_adapter/README.md) checked a dedicated
XOR-aware SAT solver against four archived compact chained-`S3` formulas on
the exact Q1438 N53/N83 bases. A direct input would silently drop CNF clauses
longer than four in this upstream solver. Q1444 uses audited shared-prefix OR
gates to preserve every clause and XOR row, fixes its ignored unit-propagation
failure, and independently checks known-witness models. The frozen binary
and formula hashes are in its protocol. Both known-satisfiable controls and
both ordinary cells reached the 60-second cap without a model. The ordinary
N53/N83 branch-counter checkpoint lower bounds are 917,504 and 524,288;
these are search-node diagnostics, not field operations or successful solve
costs. The Q1444 method keeps one witness or independent anchor fixed and
does not change the joint ordinary-query search pattern. It therefore does
not pass the target-conditioned four-point witness gate or support a complete
N131 projection.

### Q1445 pair-table control on the exact dense bases

The [Q1445 matched-input control](q1445_matched_pair_table/README.md) runs
the signed-Frobenius four-point pair table on Q1438's exact W≤4 N53 and
W≤6 N83 bases and the same ordinary public targets as Q1444. Its frozen
N53 cell builds 500,000 target-independent pair samples, then finds one
independently verified four-distinct-column ordinary relation after 54,545
target-dependent pair samples. The query interval is 6.748 exploratory
seconds; table preparation is a separate 43.188 seconds. The N83 cell
builds 10,000 pair samples and stops after 10,000 target-dependent samples
with zero key hits and no relation. Its table and query intervals are 9.582
and 10.032 exploratory seconds. Q1445's N83 sampler draws from the complete
exact base by uniform sparse-x rejection, not from a smaller cached subset.

This provides the previously missing matched-base pair-table comparator,
but no N83 successful solve, population relation yield, novel-row rate, or
N53-to-N83 successful-cost fit. The N53 relation is one stage witness; the
pair-table method remains subject to Q1443's target-oblivious-first-pair
bound. Q1445 keeps `candidate_id: null`, complete N131 `2^x: null`, and the
challenge gate closed.

### Q1446 target-linked span checks on both pairs

The [Q1446 frozen solver](q1446_joint_pair_span/README.md) fixes the
target-linked pair intermediates, interleaves decisions across all four
leaves, and applies Q1432's sound cached sparse-pair span check to both
partial pairs. Its exact Q1438 N53/N83 known-witness controls pass; a
separate partially pinned N53 control invokes both pair filters while
preserving the witness. This is a changed search order on the same dense
bases and ordinary public targets as Q1445, still using a compact chained
`S3` rather than expanded `S5`.

Both unpinned ordinary cells reach the 60-second native cap without a
relation. N53 performs 265,256/4,612 span checks on pairs 0/1; N83 performs
56,491/5,509. The independent audit replays sampled rejection claims from
both pairs. Neither cell completes a pair or activates more than one
target-linked final root. The new filter therefore reaches both partial
pairs but does not solve the intermediate-choice bottleneck. These censored
rows provide operation and memory diagnostics, not a successful-cost or
natural-yield measurement. The complete N131 `2^x` remains null and the
challenge gate stays closed.

### Q1447 uniform-midpoint support screen

The [Q1447 analytic screen](q1447_midpoint_support/README.md) tests a
tempting repair to Q1446: restart with uniformly sampled first-pair
intermediate x coordinates. On the exact N131 W≤6 base, at most
`2^-67.778` of raw x choices can be first-pair sums, even after allowing
repeated leaves and giving all later search a free oracle. For any fixed
public target, 95% success therefore needs at least `2^67.704`
abstract midpoint trials under this random-choice policy. The conditional
selected W7 size still needs `2^65.969`. The pinned N53/N83 bounds are
`2^18.314` and `2^27.717` trials. These are support bounds, not solver
timings or calibrated field operations. They exclude uniform restarts as
the next N131 method; target-guided joint search remains outside the bound.
No complete N131 `2^x` has been measured.

### Q1448 torsion-symmetrized five-input SAT stage

The [Q1448 frozen stage](q1448_torsion_phi5/README.md) applies the
published characteristic-two, two-torsion symmetrized polynomial to four
sparse leaves and every archived raw target preimage. It keeps the exact
Q1438 N53 W≤4 and N83 W≤6 factor bases, curves, public targets, and
workload IDs. The compact invariant circuit directly couples all five x
coordinates, without sampling a pair midpoint or expanding ordinary `S5`.
Independent pinned controls pass on both curves.

The ordinary N53 formula has 184,858 variables and 695,821 clauses;
N83 has 451,997 variables and 1,650,799 clauses. CaDiCaL reaches its
60-second wall cap on both without a model or verified relation. N53 is
known satisfiable from an archived ordinary witness, so its censored run
exposes solver cost rather than a missing decomposition. The measured
solver intervals are 60.115 and 60.205 seconds, with 193,838 and 37,648
conflicts respectively. The runner's larger inclusive intervals include
CNF archive compression and are not headline one-target IC times. These
are exploratory stage diagnostics on an unisolated CPU. They do not give
a natural relation rate, successful N53-to-N83 solve growth, or a complete
N131 `2^x`.

### Q1449 native-XOR representation of the phi5 stage

The [Q1449 frozen stage](q1449_phi5_native_xor/README.md) keeps Q1448's
exact ordinary N53/N83 queries and compact field circuit, but passes its
XOR equations directly to CryptoMiniSat. Fully pinned controls replay as
verified relations at both degrees. The ordinary XCNFs have 62,428 /
150,707 variables and 2,226 / 3,486 native XOR rows at N53 / N83,
respectively. Both ordinary processes reach the external 65-second
safeguard without a model or relation. Their target-dependent stage
intervals are 65.850 / 65.874 seconds on an unisolated host.

The logs explain why native XOR alone did not test the intended field
linear algebra: CryptoMiniSat used **zero** Gaussian matrices. Its
default 1,000-column limit rejects even the small N53 53×2,809 and N83
83×6,889 multiplication components. Final exact operation counters are
missing because the external safeguard terminated each process; last
restart conflict counts are only rounded partial progress. Q1449 does
not measure natural yield or a successful-solve growth rate. The
complete N131 `2^x` remains null.

### Q1450 bounded Gaussian matrices in the phi5 stage

The [Q1450 frozen stage](q1450_phi5_gauss/README.md) retains Q1449's
exact XCNFs and ordinary targets but admits up to eight Gaussian
matrices of at most 512 rows and 8,192 columns. Partially pinned
controls verify matrix activation. The ordinary N53 and N83 solver
logs report six and five active matrices, respectively; N53 also logs
Gaussian propagation and conflicts. Both cells still reach the
external 65-second safeguard without a model or verified relation.
The target-dependent stage intervals are 66.272 and 67.278 seconds
on an unisolated host. This establishes that local multiplication
matrix activation alone does not solve the ordinary query within the
frozen cap. Natural relation yield, a successful solve trend, and the
complete N131 `2^x` remain unknown.

### Q1451 fixed public-target preimage in the phi5 stage

The [Q1451 frozen stage](q1451_phi5_fixed_target/README.md) substitutes
ordinary raw target preimage index 0 as a field constant before building
the phi5 circuit. The N53 and N83 formulas use about 19% fewer AND gates
than Q1450 and pass fully pinned relation controls. The ordinary cells
activate five Gaussian matrices each, but both reach the external
65-second safeguard without a model or verified relation. Q1451 screens
one of 428 N53 preimages and one of four N83 preimages; a timeout on
one slice says nothing about whole-target relation yield. Its
target-dependent stage intervals are 66.001 and 68.361 seconds on an
unisolated host. The successful-solve growth rate and complete N131
`2^x` remain unknown.

### Q1452 known-satisfiable N53 target preimage

The [Q1452 frozen stage](q1452_known_satisfiable_phi5/README.md) keeps
Q1451's exact N53 ordinary target and solver but selects raw preimage
201, whose four-point witness is archived and group-verified. All four
leaves remain unpinned in the ordinary run. Five Gaussian matrices
activate and the solver reaches about 369K rounded conflicts before
the 65-second external safeguard, without a model. The target-dependent
stage interval is 65.263 seconds; child CPU is 50.491 seconds on this
unisolated host. A valid relation exists in this selected slice, so
constant-target substitution alone has not produced a successful
ordinary decomposition under the frozen cap. The cost of a successful
decomposition and complete N131 `2^x` remain unknown.

### Q1453 division-free projective phi5 circuit

The [Q1453 frozen stage](q1453_projective_phi5/README.md) clears the
four leaf-inverse denominators algebraically and evaluates the same
five-input phi invariant from sparse x coordinates. The identity is
checked on random tuples and archived witnesses at N53/N83; pinned SAT
controls replay exact group relations. The projective circuit has about
70% more AND gates than the inverse-constrained baseline. Both ordinary
cells reach the 65-second external safeguard without a model: N53 on
its known-satisfiable preimage 201, N83 on ordinary preimage 0. The
charged stage intervals are 65.276 and 67.119 seconds on an unisolated
host. The complete N131 `2^x` remains unknown.

### Q1454 measured N53 conflict-cap search

The [Q1454 frozen stage](q1454_phi5_conflict_cap/README.md) gives
Q1452's byte-identical, known-satisfiable N53 ordinary XCNF enough
wall time to reach its one-million-conflict cap. CryptoMiniSat exits
`INDETERMINATE` after exactly 1,000,002 conflicts and 1,367,589
decisions without a model. The target-dependent stage wall interval is
136.863 seconds on an unisolated host. A supplementary audit explains
the native exit code 15 while preserving the frozen runner's raw
`solver_error` label. This is a lower bound on this solver's search
prefix in SAT conflict units, not a successful decomposition cost or
a degree-131 field-operation estimate. The complete `2^x` remains
unknown.

### Q1455 bounded joint pair-output join

The [Q1455 frozen stage](q1455_joint_tail/README.md) implements an exact
target-conditioned join over both sparse-pair output sets while their `S3`
intermediates remain unfixed. Exhaustive N3 and archived N53/N83 controls
pass; the native propagator independently replays verified four-point
relations from both partially freed witnesses. Its five-cell archive audit
also checks sampled no-chain clauses against the separate Python join.
The N53 known-satisfiable slice and full ordinary N53/N83 cells all reach
their 60-second solver cap without a relation. Their 325, 333, and 421
observed partial states respectively all exceed the frozen pair-domain cap,
so the joint rule performs zero ordinary feasibility checks. This is a
specific eligibility bottleneck, not a measured successful-solve cost.

### Q1456 exact joint-domain profile

The [Q1456 frozen diagnostic](q1456_joint_domain_profile/README.md)
replays Q1455's same N53 known-satisfiable and full ordinary N53/N83
inputs for 15 seconds while recording every distinct partial state with
unfixed intermediates. An independent audit recomputes all completion
counts. The smallest larger-pair domains are 1,300 on both N53 inputs and
3,081 on N83. A cap of 4,096 would admit 6, 6, and 1 states respectively
in those recorded prefixes; Q1455's smaller caps admit none. This gives
a concrete next solver variant, with no successful decomposition or N131
work exponent yet.

### Q1457 bounded joint join at cap 4,096

The [Q1457 frozen stage](q1457_joint_cap4096/README.md) changes only the
pair-candidate cap on Q1455's same binary and archived inputs. Its two
partially freed witness controls still return independently verified group
relations. The unpinned known-satisfiable N53 slice and full ordinary
N53/N83 targets all reach the 60-second solver cap with no model. The exact
joint rule fires 2, 2, and 1 times respectively, and every retained
`no_chain` rejection is independently replayed. The full ordinary N53
native interval spends 708,027 field multiplications, 4,315,076 squares,
and 50,976 inversions, but this is a censored search prefix, not a
successful-decomposition cost. Most partial states still exceed the cap:
405/407, 298/300, and 403/404. The complete N131 `2^x` remains unknown.

### Q1458 batched S3 root inversions

The [Q1458 frozen stage](q1458_batch_roots/README.md) retains Q1457's
exact inputs, cap, decision policy, and resource limits while batching
the joint rule's S3 inversions. Deterministic N53/N83 root panels match
every serial root; both archived partial-witness controls return verified
group relations. A paired archive audit confirms Q1457 and Q1458 made
the same exact joint checks on the same retained rejection states. On
the N53 ordinary states, joint-rule inversions fall from 18,953 to 12
and field squares from 1,729,118 to 744,186. On N83 they fall from
12,168 to 6 inversions and 1,676,142 to 678,858 squares. All three
unpinned cells still hit the 60-second cap without a relation, so this
is a measured arithmetic improvement on censored prefixes, not a
successful-decomposition cost or a controlled wall-time speedup.

### Q1459 exact leaf-lift admission screen

The [Q1459 frozen diagnostic](q1459_leaf_lift_screen/README.md) applies
the exact nonzero-x curve-lift test to each manageable sparse leaf domain
before forming pair candidate products. An independent native field
implementation checks every distinct x in the screened domains. On the
archived Q1456 partial states, the unchanged 4,096 pair cap admits
6→6 N53 known-satisfiable states, 6→6 N53 ordinary states, and 1→2 N83
ordinary states after filtering. The new N83 admission reduces each pair
product from `79²=6,241` to `39²=1,521`. This is a sound but narrow
eligibility gain, not a solver run or a measured relation.

### Q1460 fixed-state target-x support screen

The [Q1460 frozen diagnostic](q1460_fixed_state_support/README.md)
enumerates the exact pair-intermediate `S3` x sets on every Q1459
cap-admitted archived state. A fixed state with at most 4,096 completed
leaf pairs on each side can support no more than `2^27` raw target x
values. The observed maximum is 3,385,202 for N53 raw states (781,250
after lift filtering) and 4,626,882 for N83 raw or lift-filtered states.
Independent Sage replay matches the native midpoint counts on one N53
and one N83 state. These are **fixed-state** x-only coverage bounds, not
ordinary-query success probabilities or an adaptive target-guided solver
lower bound. No new relation, successful-decomposition cost, or N131
complete-work exponent follows.
The [post-result exact-set audit](q1460_fixed_state_support/overlap_result.json)
also finds that Q1459's newly admitted N83 state has the same two
midpoint sets as an already admitted raw state. It adds no new x-only
target support in that archived prefix, although earlier propagation on
a changed solver trail remains unmeasured.

### Q1461 sparse-sum inversion and Q1462 ordinary SAT integration

The [Q1461 exact kernel](q1461_sparse_sum_inverse/README.md) fixes one
nonzero `S3` midpoint, enumerates sparse leaf XOR sums, and recovers all
compatible leaf pairs by binary linear algebra. It recovers a planted pair
at N53 and N83 and matches direct enumeration on 16 archived ordinary
partial states per degree. Those 32 states contain no pair. Its exact
primitive counts are a fixed-midpoint stage diagnostic, not work per
successful decomposition.

The [Q1462 frozen solver](q1462_sparse_sum_sat/README.md) installs this
rule in Q1446's target-linked mids-first SAT search under a 100,000-sum
cap. It reaches actual ordinary states with 67,677 N53 and 249,719 N83
direct pair completions, beyond the older 4,096-pair admission cap.
Across the frozen 60-second ordinary cells, it checks 2,070 N53 and 1,357
N83 partial pairs; every exact check rejects and neither cell recovers a
relation. Forty-eight retained rejections agree with independent direct
pair enumeration. The matched Q1445 pair table found one verified N53
relation on the same target and base, with a different query law and
preparation cost; its N83 cell also found none. These outcomes supply no
successful N83 cost, natural rank yield, or complete N131 `2^x`.

## Next goal

The next goal is **one independently verified four-point relation from the
unfixed, known-satisfiable N53 preimage 201**, with exact primitive counts
and a charged target-dependent stage interval. Q1452 and Q1454 could not
recover that unpinned witness through the phi5/XCNF route. Q1455's joint
rule never fired on unpinned inputs at its original cap. Q1457 activates
the rule at N53/N83 but reaches only two N53 and one N83 joint checks in
60 seconds, without a relation. Its N53 ordinary run spends over 4.3
million native field squares in that censored interval. Another blind cap
increase is not an adequate solver strategy. Q1458 removes nearly all
joint-rule inversions on those same states but still recovers no unpinned
relation, so arithmetic-only tuning also leaves the main gap.
Q1459 shows that exact single-leaf curve-lift filtering adds only one
admitted N83 state in the archived prefixes and none at N53.
Q1460 bounds each admitted fixed state's raw-target x support and
quantifies why bounded admission alone is a limited search mechanism;
the target-dependent SAT trail prevents interpreting that bound as a
natural relation-yield estimate.
Q1461 makes larger fixed-midpoint checks exact, and Q1462 runs thousands
of them on ordinary N53/N83 queries, but every check rejects and both
cells remain censored. Q1456's large-domain counts leave midpoints free;
they cannot be used as Q1461 fixed-midpoint admissions. The next algorithm
must couple many possible midpoint values to the public target instead of
spending a full search prefix on one fixed midpoint at a time.

The [Q1463 free-midpoint rank screen](q1463_free_midpoint_rank/README.md)
tests a direct linear-span route on the archived Q1456 partial states.
Both pair-product coefficient spans have full field rank in all 65 state
rows. The exact reachable midpoint sets in all 13 states within a
4,096-pair cap also have full affine rank on both sides; independent Sage
replays the smallest N53 and N83 cases. This rules out an unrestricted
monomial-span rejection on those prefixes and any proper affine container
for their bounded midpoint sets. It does not rule out a weight-aware
nonlinear joint rule or measure a new ordinary relation.

The [Q1464 wide exact join](q1464_joint_cap250k/README.md) raises only
Q1458's pair-candidate cap to 250,000. It activates four N53 and two N83
target-linked checks within the same 60-second native limit, versus two
and one at cap 4,096. All checks reject their partial state; the three
unpinned cells remain censored without a relation. A separate
post-result serial-root audit independently confirms zero x-only chains
in the first wide N53 and N83 ordinary rejection states, with 67,677 and
249,719 pair candidates per side. The larger cap improves exact-state
coverage but still supplies neither a successful N83 decomposition nor a
natural useful-row rate.

A concrete successor should process **large partial pair-output domains**
without enumerating every pair combination. First derive and independently
verify a sound target-conditioned necessary condition on partial leaves,
then incorporate it as an incremental propagation or branching rule. Freeze
the same N53 selected-preimage and full ordinary N53/N83 workloads, preserve
all failures, and compare root calls and verified relations in a common
accounting unit. If the N53 known-satisfiable slice is recovered, proceed
to enough ordinary queries to measure natural yield and rank; a single
control relation does not estimate those rates. Q1447 excludes uniformly
restarting first-pair midpoints under the declared bases, and Q1416's pure
pair-index model costs roughly `2^89.36` logical actions at N131; neither
is a lower bound on target-guided algebraic search. The challenge stays
closed until the complete N131 solve can be charged below `2^61`.

Freeze the stage before ordinary queries. The first measurable gate is the
unpinned archived N53 ordinary target, which Q1301 already proved
representable. The second is an independently verified ordinary relation on
the exact Q1438 N83 W≤6 base, with a pre-registered fresh-target panel if
the fixed N83 target has no representation. Keep the older Q1325 W≤5 base as
a separately labeled factor-base comparison. Preserve failed queries, raw
operations, memory, and matched pair-table receipts.

For work planning, Q1414's exact-base uniform-query model allows less than
`2^33.36` abstract work units per query under a `2^61` total cap **even
when every other phase costs zero**. This is a necessary affordability
ceiling for that model, not a measured point-decomposition cost or a
complete solve projection. The new method needs a measured natural yield
and a calibrated N53/N83 cost trend before any degree-131 `2^x` is credible.

Only after the N83 gate passes should a fresh ordinary-query panel measure
verified useful-row yield, novel rank per query, and charged cost per useful
row. Calibrate field arithmetic, conversion, hashing and point work into a
declared common unit; add exact-base construction, relation collection, final
matrix build/solve, target descent, and scalar replay. Keep the complete
\(2^x\) unknown until every term is measured or bounded. Dispatch the
challenge only if the complete degree-131 projection is credibly below
\(2^{61}\).

### Q1467 density-matched four-point solver gate

[Q1467](q1467_density_bridge/README.md) selects an exact N53 factor base
with 2,756 usable subgroup points and 26 folded columns. Its four-summand
counting upper bound is 0.11447 per uniform target, within 0.0142 bits of
the exact N131 W≤6 reference bound of 0.11335. The exact N83 W≤4 base has
1,934,066 usable points, 11,651 columns, and counting upper bound 0.24113.
These are relation-supply bounds, not measured solver success rates.

Six frozen compact chained-\(S_3\) cells were run with the same Q1466 native
solver and a 60-second cap. Fully pinned planted controls independently
verify at both degrees. Both unpinned known-representable controls and both
ordinary queries reach the cap without a model. The N53 unpinned and ordinary
cells each make 49 exact no-chain checks; the N83 cells each make one. The
archive audit preserves the first replay-wrapper failure and verifies the
corrected revision-2 receipts. The current solver under this cap does not
meet the first successful-unpinned-decomposition gate. No natural useful-row
rate, matched pair-table result, successful N83 cost, or complete N131 `2^x`
is available. The challenge remains closed.

### Q1468 exact N53 pair-sum oracle

[Q1468](q1468_n53_pair_oracle/README.md) tests `PDP4mitm` on the same exact
N53 base and public targets as Q1467. A full table contains all 3,651,700
cross-column pair sums. It independently verifies a four-distinct-column
relation for Q1467's unpinned planted target, while exhaustive lookup finds
no four-distinct-column sum for Q1467's ordinary target. The latter result
means that one SAT timeout cannot be interpreted as a successful-solver cost;
the planted timeout still demonstrates solver failure on a known-solution
input. The two single-target pair-table query phases take 1.958 and 4.334
seconds on an unisolated host, with table setup charged separately. One
ordinary target supplies no natural yield rate or rank trend. N83 and the
complete N131 `2^x` remain unresolved.

### Q1469 ordinary N53 yield and rank panel

[Q1469](q1469_n53_yield_panel/README.md) runs that same exact pair oracle
on 128 new seeded ordinary N53 subgroup targets, building a fresh complete
3,651,700-pair table for each. It finds and independently replays 13
four-distinct-column relations, proves 115 absences by complete scan, and
obtains 13 novel rows among 26 folded columns. The observed relation yield
is 10.156% (model-based Wilson 95% interval 6.032%–16.602%). Including all
failed queries, the target-query work per early novel row is 163.740 million
field multiplications, 33.151 million squarings, and 7,999 inversions; fresh
table preparation is charged separately. Wall times are exploratory.

On the exact N131 W≤6 base, this **complete-table** design requires
21,514,403,416,657,745,244 pair entries (`2^64.222`) before a target query,
above a `2^61` entry-materialization cap. This does not bound compact
target-guided methods. N83 successful ordinary work and natural yield,
late-rank behavior, final matrix work, target descent, and scalar replay
remain unknown, so the complete N131 `2^x` and challenge gate remain open
questions.

### Q1470 extended N83 known-solution control

[Q1470](q1470_n83_long_control/README.md) reruns Q1467's exact
known-representable N83 unpinned CNF with a 600-second native wall cap. It
again stops without a model, after 159,108 SAT conflicts and one exact
joint-chain check. Its field primitive calls are identical to the earlier
60-second run even though conflicts and peak memory rise substantially.
Thus field calls alone miss the dominant SAT search work in this hybrid
solver. The result is a censored correctness control, not a natural N83
relation yield or successful decomposition cost. The complete N131 `2^x`
remains unknown.

## Reproduction

From this repository worktree, first save checked runtime information:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1324_sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/native_root_sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python -m unittest discover -s experiments/compact-s3-m4-20261003 -p test_chain_s3.py -v
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1324_inputs.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/enumerate_n83_weight5_full.py --self-test
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1325_inputs.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/run_q1326_nested_base_probe.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/screen_n83_four_point_support.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1324_base.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1325_full_base.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/derive_onb_poly_bridge.py --n 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/derive_onb_poly_bridge.py --n 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_onb_poly_bridge.py --n 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_onb_poly_bridge.py --n 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/export_native_root_inputs.py --n 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/export_native_root_inputs.py --n 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_native_s3_root.py --n 53 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_native_s3_root.py --n 83 --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/make_n83_native_planted_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_n83_q1329_native_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/freeze_batch_root_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/freeze_batch_planted_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_native_s3_root.py --n 53 --variant batch --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_native_s3_root.py --n 83 --variant batch --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_n83_q1329_native_control.py --variant batch --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/export_q1400_pair_inputs.py --check
python3 experiments/compact-s3-m4-20261003/build_q1400_pair_comparator.py --check
python3 experiments/compact-s3-m4-20261003/run_q1400_pair_comparator.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/make_q1401_pair_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1401_pair_control.py --check
python3 experiments/compact-s3-m4-20261003/screen_q1402_fixed_pair_family.py --check
python3 experiments/compact-s3-m4-20261003/derive_q1400_primitive_calls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1403_ordered_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1403_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1404_raw_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1404_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1408_balanced_control.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1408_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1410_n53_balanced.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1410_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1412_n53_ordered.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1412_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/derive_q1413_base_calls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/screen_q1414_exact_uniform_query_bound.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/screen_q1416_exact_pair_index.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1415_gauss_n53.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_q1415_stage_comparison.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1413_q1416_archive.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_frozen_artifacts.py
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/build.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/prepare_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/run.py --check
python3 experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/validate_controls.py --check
python3 experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1462_sparse_sum_sat/verify_archive.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

All new or resumed local Sage jobs use the repository's checked launcher.
For the frozen SAT runs, see the exact seeds, bounds, and source hashes in
`protocol.json` and the `runs/*_frozen.json` receipts. The recorded wall
interval begins at formula construction and includes every target-dependent
attempt; fixture construction and launcher startup are excluded.
