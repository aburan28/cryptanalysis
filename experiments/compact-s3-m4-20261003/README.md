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

## Work accounting and decision

[`work_ledger.json`](work_ledger.json) separates the measured pair counts
from the unknown complete cost. Under a simple independent, uniform
pair-sum-orbit model, a balanced random quotient pair table at n=131 would
need roughly \(2^{61.48}\) *logical pair samples* for one expected match.
This is a heuristic for the sampled pair-table method, not a measured lower
bound, a field-operation conversion, or a projection for the SAT solver.
It already excludes base construction, final LA, and target recovery.

The complete n=131 work exponent remains **unknown**. The corrected SAT stage
is censored at both measured field degrees; natural relation yield, novel rank,
cost per useful row, final matrix solving, target descent, and independent
scalar replay are absent. There is therefore no defensible complete-solve
upper projection below \(2^{61}\), and the degree-131 challenge gate remains
closed. Existing complete ECDLP claims cannot be inferred from a relation
stage or a planted witness.

The next useful goal is a **noncensored ordinary public-target
four-summand decomposition**, first at n=53 and then at n=83, using the exact
same base and cofactor-preimage policy. The n=53 frozen point is known to have
a valid raw witness, so it gives a direct search test. The orbit and leaf
ordering SAT variants are now tested without a natural success; a new
solver mechanism should be benchmarked against the matched n=53 pair index
and the full-coset SAT circuit on the same target. Keep all failed attempts
and measure Boolean operations, field-operation conversion, and wall time;
collect enough independent ordinary queries to estimate useful relation and
novel-rank rates with uncertainty.
Only then fit an n=131 stage cost and add matrix, descent, and replay charges.
If the fitted complete cost is credibly below \(2^{61}\) in a named operation
unit, the challenge run is justified; otherwise the experiment is a no-go
for this solver family.

## Reproduction

From this repository worktree, first save checked runtime information:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/sage_runtime_info.json
python3 -m unittest discover -s experiments/compact-s3-m4-20261003 -p test_chain_s3.py -v
python3 experiments/compact-s3-m4-20261003/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/verify_frozen_artifacts.py
python3 -c 'import sys; sys.path.insert(0, "experiments/compact-s3-m4-20261003"); from verify_weight_base import verify; assert verify("experiments/compact-s3-m4-20261003/bases/n53_weight3_orbits.json.gz")["pass"]'
python3 -c 'import sys; sys.path.insert(0, "experiments/compact-s3-m4-20261003"); from verify_weight_base import verify; assert verify("experiments/compact-s3-m4-20261003/bases/n83_weight4_orbits.json.gz")["pass"]'
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

All new or resumed local Sage jobs use the repository's checked launcher.
For the frozen SAT runs, see the exact seeds, bounds, and source hashes in
`protocol.json` and the `runs/*_frozen.json` receipts. The recorded wall
interval begins at formula construction and includes every target-dependent
attempt; fixture construction and launcher startup are excluded.
