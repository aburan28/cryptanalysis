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

The exact n=53 curve cofactor is **428**; the n=83 cofactor is **4**.
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
comparison, not a solver-work ratio or a complete-solve projection. The
full W≤6 base is still unenumerated, so both Q1303 and Q1318 keep
`candidate_id: null` and an unknown exact base digest.

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
projection. Q1303's exact \(B\) and digest remain unknown.

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
enumerated, so Q1303 retains `candidate_id: null`, exact `B: null`, and a
null enumerated-set digest.
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
base count and digest remain unknown.

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

## Next goal

The next gate is an **ordinary N83 four-point relation on the exact Q1325
base from a search that avoids both the full \(K^2n\) index and Q1331's
fixed two-million-state support limit**. Q1329 has now
validated the native S3 search on an unpinned, known-satisfiable N83 target;
Q1401 has independently validated the quotient-pair search on the exact
Q1325 base with a planted public target. Q1403's ordered implicit-base
SAT formula still cannot recover its unpinned known-satisfiable control
within 60 seconds or the ordinary target within 120 seconds. Q1400's
ordinary no-hit and tiny fixed-rectangle support bound leave ordinary
relation yield unmeasured.
Run frozen ordinary single-target workloads under identical operation and
memory limits, retaining all zero-yield cells and independently verifying
any relations.
The design needs measurable useful-row yield and novel rank per query,
including failed attempts. Merely increasing the current sampled index cap
cannot justify extrapolation to its 2.9-trillion-state N83 full index.

After that, freeze an exact or certified N131 base and calibrate inversion,
multiplication, conversion, hashing, and point costs in a common operation
unit. Add base construction, relation collection, final matrix rank and
solve, target descent, and scalar replay to a complete \(2^x\) ledger.
Keep \(x\) unknown until every required term is measured or bounded. A
challenge run is justified only if the **complete** fitted cost is
credibly below \(2^{61}\).

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
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_frozen_artifacts.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

All new or resumed local Sage jobs use the repository's checked launcher.
For the frozen SAT runs, see the exact seeds, bounds, and source hashes in
`protocol.json` and the `runs/*_frozen.json` receipts. The recorded wall
interval begins at formula construction and includes every target-dependent
attempt; fixture construction and launcher startup are excluded.
