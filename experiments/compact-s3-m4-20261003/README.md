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
A second n=83 encoding represents the same exact base implicitly through
cofactor-four projection of sparse rational x values. It reduced the CNF
clause count but also produced no unassisted relation within its caps.
An exact half-trace root circuit for the first two S3 links was tested next;
its ordinary n=83 query also remained censored.
A full point-addition circuit then made the intermediate sums deterministic
once all four leaf points were fixed. Its unassisted n=53 and n=83 queries
also remained censored at 120 seconds.

## Identity and comparable inputs

[`protocol.json`](protocol.json) freezes each curve, subgroup, weight-base
policy, one-target ordinary workload, and SAT cap. The exact enumerated bases
are in `bases/`. Their compact archives contain every canonical signed-
Frobenius x-orbit key and its length, allowing reconstruction of the actual
point set and its pre-fold size. [`verify_weight_base.py`](verify_weight_base.py)
checks the archive structure, orbit arithmetic, counts, and sampled subgroup
membership. The n=53 pair-table comparator also recomputes the orbit-key
digest independently from the prior full-base enumerator.

| Proposal | Exact curve ID | Weight bound | Actual usable points \(B\) | Folded columns | Base-key SHA-256 prefix |
| --- | --- | ---: | ---: | ---: | --- |
| Q1301 | `EC1N53Ckb1hf77aab617904` | 3 | 24,062 | 227 | `05b75578ee58` |
| Q1302 | `EC1N83Ckb1h876c2921cb64` | 4 | 1,934,066 | 11,651 | `800a59307125` |
| Q1303 | `EC1N131Ckb1h6816f880945e` | proposed 6 | unknown | unknown | unknown |

The exact n=53 curve cofactor is **428**; the n=83 cofactor is **4**.
These values are read from the curve manifests when constructing raw target
preimages and subgroup points. All three designs use `isogeny: "none"`. They
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
ordinary timeout is ambiguous. Q1324's larger base raises the modeled
target coverage but also timed out without a natural relation. Neither
timeout is an observed zero relation rate for a complete collector; both
are censored solver attempts on one frozen target.

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
exact-base, larger n=83 weight-five, and implicit projected-base SAT stages
are censored; natural
relation yield, novel rank, cost per useful row, final matrix solving, target
descent, and independent scalar replay are absent. There is therefore no
defensible complete-solve upper projection below \(2^{61}\), and the
degree-131 challenge gate remains closed. Existing complete ECDLP claims
cannot be inferred from a relation stage or a planted witness.

The next useful goal is a **noncensored, independently verified ordinary
public-target four-summand decomposition from an improved leaf-choice
solver**. First recover the known-satisfiable n=53 target without pinning a
leaf, under the frozen exact base, and compare total attempts and work with
the matched pair table. Then recover at least one target on Q1324's larger
n=83 base, keeping the original Q1302 target as the matched public point
and preserving zero-yield targets in any later panel. A pure pair-index
method is already screened as too expensive at n=131; a new
hybrid or algebraic search must show a different scaling mechanism. Measure
operations, memory, natural useful-row and novel-rank rates, including all
failed attempts. Only then fit a degree-131 stage cost and add base
construction, final matrix, target descent, and scalar replay charges. A
challenge run is justified only if the **complete** fitted cost is credibly
below \(2^{61}\) in a named operation unit.

## Reproduction

From this repository worktree, first save checked runtime information:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1324_sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python -m unittest discover -s experiments/compact-s3-m4-20261003 -p test_chain_s3.py -v
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1324_inputs.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/screen_n83_four_point_support.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_q1324_base.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/verify_frozen_artifacts.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

All new or resumed local Sage jobs use the repository's checked launcher.
For the frozen SAT runs, see the exact seeds, bounds, and source hashes in
`protocol.json` and the `runs/*_frozen.json` receipts. The recorded wall
interval begins at formula construction and includes every target-dependent
attempt; fixture construction and launcher startup are excluded.
