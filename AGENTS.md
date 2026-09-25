# Agent rules for cryptanalysis experiments

## Index-calculus candidate names and measurements

Use this convention for new elliptic-curve index-calculus (IC) candidate
configurations and result tables. It names a complete pipeline, from the
mathematical instance through the recovered discrete logarithm. Existing
artifacts keep their old names; give them an ID under this convention when
they enter a new comparison. **Always** use the candidate and measurement
rules below when comparing IC variants. A campaign may impose stricter claim
rules. The [candidate catalog](experiments/ic-candidate-catalog/README.md)
contains design proposals; its [measurement contract](experiments/ic-candidate-catalog/MEASUREMENT.md)
specifies the empirical stage record and promotion gates.

### Three distinct identifiers

1. **Curve ID** identifies one exact field representation, curve, and DLP
   subgroup. Its readable form is `EC1N<n>C<curve-tag>h<12hex>`.
   `N53` means the field has `2^53` elements; it does **not**
   mean a 53-bit subgroup. `curve-tag` is a human hint, such as `kb1` for a
   Koblitz `b=1` model, never the source of truth. Hash the canonical curve
   record described below: hash `field` and `curve`, excluding the curve ID
   itself and any run data.
2. **Candidate ID** identifies one fully specified IC method on that curve.
   Use

   `IC1N<n>C<curve-tag>fb<B>PDP<m><solver>RC<collector>LA<matrix-solver>TD<descent>ISO<0|1>h<12hex>`

   For example, the *illustrative* name
   `IC1N53Ckb1fb64PDP5f4RCwalkLAbwTDdirectISO0h<12hex>` means a
   field of size `2^53`, 64 actual usable factor-base points, a five-summand
   F4 point-decomposition solver, a walk relation collector, block Wiedemann
   for the final relation matrix, direct target handling, and no isogeny
   transport. Replace `<12hex>` with the first 12 lowercase hex digits of
   SHA-256 over the canonical candidate record. Extend the digest if a
   truncated-hash collision ever occurs.
3. **Run ID** identifies a measured execution of one candidate on one frozen
   workload. Use `<candidate-id>W<12hex-workload-id>R<run-number>`. Repetitions,
   hardware, target seeds, limits, results, and artifacts belong to the run
   record; they do not silently change the candidate ID. A workload ID fixes
   its curve/subgroup, targets, input law, seeds, and cold or warm target count.
   Form the workload ID from the first 12 hex digits of SHA-256 over its
   canonical workload record.

A design proposal may use a `Q<number>` catalog ID while exact base points,
algorithm wiring, or isogeny maps are unresolved. Keep `candidate_id: null`
and all measured costs null until those gates are satisfied. A proposal ID is
never an `IC1` result, and a nominal dimension is never an actual `fb` count.
A measured PDP-stage profile of an exact base without final relation LA or
target descent (`experiments/pdp-degree-heuristics/`) also keeps
`candidate_id: null`. Label it `PS1N<n>C<curve-tag>fb<B>PDP<m><solver>h<12hex>`,
hashing its factor-base and point-decomposition records. Its run ID is
`<PS1-id>W<workload>R<run>`, and it is never an `IC1` result.

For an isogenous curve, preserve its own immutable curve ID and use the
[volcano-position and isogeny-walk convention](experiments/ic-candidate-catalog/VOLCANO_NAMING.md).
Only a proved ordinary `ell`-volcano level may appear as `V<ell>L<level>`;
`L0` is the surface, and downward/upward edges change the level by `+1`/`-1`.
Keep the ordered edge route separate from the curve ID. In characteristic
two, degree-2 routes have no ordinary `V2` level label. Unknown levels remain
`null`, not zero.

`fb<B>` is the **actual number of distinct, nonidentity, subgroup-usable
factor-base points before sign/Frobenius orbit folding**, written as a plain
decimal integer without leading zeros. Record the nominal subspace dimension
or bound, geometric point count, and effective relation-matrix column count
separately. The latter can be much smaller than `B`. Never compare
configurations by `N` and `fb` alone;
the digest distinguishes different bases or algorithms with the same counts.

There are no separators or zero-padded numbers in an ID. Structural tags
(`IC`, `N`, `C`, `PDP`, `RC`, `LA`, `TD`, `ISO`, `W`, `R`) are uppercase; values
(`kb1`, `f4`, `walk`, `bw`, etc.), the `fb` tag, and hex digits are lowercase.
The stage codes are short, stable, and recorded in the candidate manifest.
The compact ID is a label; load the manifest for the exact configuration.
Suggested codes: `PDP5f4`, `PDP5f5`, `PDP5sat`, `PDP5hybrid`, and `PDP4root`
for the compact four-summand S3 root index; `PDP2xl` for a dense Macaulay/XL
degree scan and `PDP2xlsym` for the same scan over the symmetric-function
(`e_k` in `V^(k)`) formulation, with the XL or closure mode in the manifest;
`RCwalk`, `RCsample`, `RCdirect`,
and `RCguided` for pivot-guided relation collection;
`LAbw`, `LAwied`, `LAgauss` for **final sparse relation-matrix** solving;
`TDdirect`, `TDpdp`, `TDdescent` for target handling; `ISO0` for no isogeny
transport and `ISO1` for a specified route. A solver's internal Macaulay
matrix reduction belongs under `PDP`, including its RREF/M4RI/GPU kernel. It
is not the `LA` stage. Extend the vocabulary in this file when a genuinely
new stage appears; keep the exact variant and parameters in the manifest.

### Canonical candidate record

Store one immutable, machine-readable manifest beside each candidate. Use
sorted-key, compact UTF-8 JSON for identity hashing: integers as integers,
field elements and points in one declared encoding, exact decimal strings
for nonintegral parameters, and no JSON floats, paths, timestamps,
measurements, run seeds, or `candidate_id` in the hash input.
Include these fields, using explicit `null` for unknown mathematics and
`"none"` for an intentionally absent stage:

| Section | Exact fields to retain |
| --- | --- |
| `field` | characteristic `p`, degree `n`, representation/basis, irreducible polynomial or defining modulus, and element encoding |
| `curve` | exact Weierstrass model and coefficients, curve order/trace when known, subgroup order `r`, cofactor, encoded generator `G`, target group, and the curve ID; omit the ID itself when hashing the curve record |
| `isogeny` | `none` or ordered source/target curve IDs, edge degrees, directions, explicit maps or verified map artifacts, transport of `G` and `Q`, and kernel/subgroup checks; measure transport costs in runs |
| `endomorphism` | for an ordinary curve, the endomorphism **order** conductor if proved; for each relevant prime `ell`, the volcano level `v_ell(f_End(E))` and proof/status; keep the Frobenius-order conductor separate. Use `null` if unknown, and `not_applicable` if the volcano model does not apply |
| `factor_base` | exact construction (subspace/basis, polynomial constraint, shifted bases, seeds, subgroup filtering), enumerated-set digest, nominal dimension/bound, actual usable point count `B`, sign/Frobenius quotient rule, and effective column count |
| `point_decomposition` | summand count `m`, summation polynomial/chain, Weil-descent encoding and equation order, solver family (`f4`, `f5`, `sat`, etc.), implementation/version/source digest, monomial order, internal matrix kernel, limits, and cache policy |
| `relation_collection` | target/query distribution, walk or sampling rule, filtering, verification, duplicate/dependency handling, stop criterion, and source digest |
| `relation_linear_algebra` | modulus, matrix row/column construction, orbit quotient, rank criterion, solver (`bw`, `wied`, `gauss`, etc.), implementation/version, block parameters, preconditioner, and source digest |
| `target_descent` | direct recovery or complete descent policy, recursive solvers, success/stop rules, and source digest |
| `implementation` | exact code snapshot or content hashes for every executed component and all algorithm-affecting flags |

Do not collapse an unknown conductor into `0`, or a claimed volcano level into
an unverified curve tag. A volcano level is relative to a particular `ell`;
an isogeny walk must identify its actual route. If no isogeny is used, record
`isogeny: "none"` even when endomorphism information is available.

### Measurement rows and accounting

The spreadsheet/CSV/table key is `(candidate_id, workload_id, run_id)`.
One row per run preserves failures, timeouts, and OOMs. Pair candidates on
the same curve, factor-base policy when that is the controlled variable,
target set, seeds, target count, resource limit, and accounting unit. When a
factor base or curve is the variable, state that comparison explicitly.

Keep exclusive phase costs so their sum is the charged total:

`T_cold = T_setup + T_isogeny + T_factor_base + T_precompute + T_queries + T_PDP + T_relation_check + T_matrix_build + T_relation_LA + T_target_descent + T_recovery_check`.

`T_PDP` covers relation collection and includes failed and timed-out attempts;
`T_queries` includes query generation. Target descent includes all recursive
decomposition work for the target but charges it only once. Retain attempts,
verified relations, novel rows, final rank, solved targets, memory peak,
wall time, operation counts,
conversion/calibration, and correctness certificate. `T_cold` is for the
declared target count with empty caches. For `k` targets, report any warm
amortization separately as `(shared_setup + sum(target_cost_i))/k`, naming
`k` and which costs are shared. A missing phase cost makes the end-to-end
total and speedup **unknown**, not zero.

The headline comparison is complete verified DLP cost in one calibrated
operation unit: `speedup = baseline_total / candidate_total`. Also report
`S = total_operations / sqrt(r)` and the ratios to the declared rho reference
and applicable floor, with the boundary fixed before measurement. F4/F5/SAT
solve time, coverage, or cost per useful row are stage diagnostics. Label
predictions and extrapolations separately from measurements. Put the
baseline, candidate, rho reference, correctness, total, and boundary ratios
in one table. A row with an unverified answer is not an end-to-end result.

Every empirical comparison must also retain stage measurements: actual base
size and folded columns, base construction and memory, ordinary-query PDP
status mix and cost (including failed attempts), verified relation yield,
novel rank per query and cost per useful row, matrix construction and final
LA, target descent, and scalar replay. Pair variants on frozen inputs and
resources; preserve timeouts, OOMs, and zero-yield cells. Report uncertainty
for rates and paired costs. Planted decompositions are correctness controls,
not estimates of natural relation yield. An unverified isogeny neighbor or
conductor guess is a proposal only: `ISO1` requires an explicit verified map,
ordered edge links, subgroup/log transport, and charged route costs.
