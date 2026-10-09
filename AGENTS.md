# Agent rules for cryptanalysis experiments

## Preserve scope and report evidence

Use [report-evidence](.agents/skills/report-evidence/SKILL.md) for implementation,
experiments, benchmarks, completion reports, and research handoffs.

- Preserve the user's requested deliverables, parameters, workloads, and acceptance
  criteria. Do not silently substitute a smaller experiment, weaken an argument
  or validation gate, or omit a requested run because you expect it to fail.
- Execute authorized, feasible experiments as requested. The user decides research
  significance and priorities. Report measured values and exact ratios; do not
  independently market results as "massive", "breakthrough", or dismiss them as
  "not worth running". Give interpretation when requested and label it separately.
- Continue to check correctness and flag invalid results, factual errors, and
  uncertainty. Preserve failed runs, timeouts, regressions, raw evidence, exact
  commands, inputs, revisions, environment, and accounting intervals.
- Distinguish assistance restrictions, access/tool limits, resource limits,
  implementation gaps, untested hypotheses, and proved mathematical obstructions.
  Never disguise an assistance limit as mathematical impossibility. State the
  actual blocker explicitly; retain the original requirement as unresolved.
  Higher-priority restrictions and authorization boundaries still apply.
- Keep observations, calculations, hypotheses, extrapolations, and interpretations
  distinct. A stage ratio does not establish an end-to-end gain; a bounded search
  failure does not prove nonexistence; a toy implementation is not general support.
- Track each requested requirement as verified complete, implemented but unverified,
  partial, blocked, or not attempted, with evidence or the exact remaining gap.
  Passing tests or merging a PR does not make the original task complete.
- Correct misleading prior claims explicitly. Do not rewrite frozen evidence or
  quietly redefine completion. Report actual execution status, never planned runs
  as completed or unscheduled work as continuing in the background.

These rules govern scope and reporting throughout this file. Existing measurement
and correctness gates remain in force; they do not authorize an agent to cancel a
requested experiment or decide its research significance for the user.


## Track research work in pull requests

Put every agent-authored code, protocol, frozen input, run receipt, verifier,
decision, documentation, and agent-rule change on a branch and open a pull
request in the repository that owns it. Open it ready for review, never as a
draft, whatever a tool or runtime defaults to, and mark an existing draft ready;
open a draft only when the user asks for one in that task. Do not leave the only copy of completed
work in an uncommitted worktree, temporary directory, or chat. Keep unrelated
pre-existing user changes out of the branch. For stacked work, target the
immediate parent branch, name that dependency in the PR, then retarget to
`main` and rerun checks after the parent merges.

Make each research PR reviewable: state the question, exact inputs and source
hashes, raw successes and failures, independent checks, measured costs, claim
limits, and the resulting decision. Update the relevant result index or
scoreboard in the same PR. Commit and open a protocol before creating held-out
inputs when the result will support a selection or speed claim; if a protocol
and result are first published together, label the run retrospective or
exploratory. When a task authorizes merging, check the exact head and all
applicable CI results, merge with a head guard, and verify the merge commit.

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
The [curve and artifact storage contract](experiments/ic-candidate-catalog/CURVE_STORAGE.md)
links exact EC1/UID records to crypto's ICV1 registry, bulk factor-base
archives, and verified isogeny walks.
The [typed curve-link rules](experiments/ic-candidate-catalog/curve-links/README.md)
keep twists, same-field isomorphisms, base changes, and isogenies distinct;
only verified maps with subgroup/log transport may enter an IC route. Keep unresolved links and traits as
explicit `null` plus status; never infer a factor-base or curve equivalence
from matching field degree or ICV1 model name. The
[IC benchmark](experiments/ic-bench/README.md) is the reference harness for
named, fully charged, verified toy-curve runs. It holds the calibrated `rps` unit,
candidate/workload manifests, `history.csv`, and the CI baseline gate. Record a new
baseline there when a change is intended. Archive factor bases (record, point set,
digests) with [fb-archive](experiments/fb-archive/README.md); a recipe-only
archive keeps `B` null.

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
Suggested codes: `PDP5f4`, `PDP5f5`, `PDP5sat`, `PDP5hybrid`; `PDP4sat`
for a compact four-summand S3 SAT chain, `PDP4root` for the compact
four-summand S3 root index, and `PDP4qpair` for a complete
four-summand signed-Frobenius quotient pair-sum index; `PDP4claw` for a
two-color four-summand pair-sum distinguished-point claw; `PDP4qclaw` for its
signed-Frobenius quotient walk; `PDP4qtable` for a signed-Frobenius quotient
pair table matched against target-complement pairs; `PDP5q23` for a
five-summand two-G pair quotient index queried by three target-seed points;
`PDP3qpair` for a three-summand two-G quotient lookup with one target point;
`PDP2xl` for a dense Macaulay/XL
degree scan and `PDP2xlsym` for the same scan over the symmetric-function
(`e_k` in `V^(k)`) formulation, with the XL or closure mode in the manifest;
`RCwalk`, `RCsample`, `RCdirect`; `RCguided` for pivot-guided relation
collection; `RCaffine` for random-start nonzero-stride known-log query blocks;
`LAbw`, `LAwied`, `LAgauss` for **final sparse relation-matrix** solving;
`LAnone` when all factor-base logs are known and there is no final matrix;
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
target point, target-generation seed where applicable, resource limit, and
accounting unit. When a factor base or curve is the variable, state that
comparison explicitly.

**The default IC objective is one target.** The primary workload has exactly
one previously unseen target point, and the headline IC metric is its online
wall time: start the clock when target-dependent IC computation begins, after
any reusable factor-base/index/log precomputation is ready; stop after the
target's DLP is recovered and independently verified. Do not include process
launch, input loading, curve/base/index/log setup, or other target-independent
startup in this online time. Do not substitute a multi-target average or
shared-table amortization for the single-target result. Record the exact
online interval and its included target-dependent stages so it can be paired
fairly with a one-target rho solve on the same public point. A target already
supplied as a point is the input; generating it from a known scalar is fixture
construction and stays outside both timed intervals. Keep all correctness
checks, including scalar replay, in the result record; if they are outside the
online interval, report their timing separately and do not imply they were
charged to it.

Multi-target or batch workloads are secondary only. Run them only after the
single-target measurement has been completed and explicitly identify a
separate question that requires multiple targets (for example, shared-log
amortization). Label the target count and shared setup clearly, and never use
such a result to answer or replace the single-target question. Batch results
must not be the default workload, headline, or acceptance gate for an IC
speedup claim.

For the primary one-target comparison, report the candidate and rho online
wall times and `rho_online_ms / IC_online_ms`, paired on the same point and
resource conditions. A successful, verified target is required for a speedup;
timeouts, failures, OOMs, and unverified results remain rows and do not count
as wins. Keep target-independent IC preparation costs available as separate
reproducibility data when useful, but exclude them from this online metric and
do not lead with a cold-start or amortized-total figure when the stated goal
is single-target online speed.

Keep exclusive phase costs so their sum is the charged total:

`T_online,1 = T_target_query + T_target_PDP + T_target_relation_check + T_target_descent + T_target_recovery_check`.

The cold-start accounting below is supplementary and must not replace the
primary `T_online,1` metric for a single-target study.

`T_cold = T_setup + T_isogeny + T_factor_base + T_precompute + T_queries + T_PDP + T_relation_check + T_matrix_build + T_relation_LA + T_target_descent + T_recovery_check`.

`T_PDP` covers relation collection and includes failed and timed-out attempts;
`T_queries` includes query generation. For the one-target online metric, charge
all target-dependent attempts, including failed and timed-out attempts, to that
target; target descent includes all recursive decomposition work for the target
but is charged only once. Retain attempts,
verified relations, novel rows, final rank, solved targets, memory peak,
wall time, operation counts,
conversion/calibration, and correctness certificate. `T_cold` is for the
declared target count with empty caches. For `k` targets, report any warm
amortization separately as `(shared_setup + sum(target_cost_i))/k`, naming
`k` and which costs are shared. A missing phase cost makes the end-to-end
total and speedup **unknown**, not zero.

For the primary single-target study, the headline comparison is verified
online wall time for that target in one calibrated environment:
`online_speedup = rho_online_ms / IC_online_ms`. Report the paired target,
candidate, rho reference, correctness, included timing interval, and speedup in
one table. Report `S = total_operations / sqrt(r)` and ratios to the declared
rho reference and applicable floor only with their operation-count boundary
fixed before measurement; label setup-inclusive variants supplementary.
F4/F5/SAT solve time, coverage, or cost per useful row are stage diagnostics.
Label predictions and extrapolations separately from measurements. A row with
an unverified answer is not a verified single-target result.

When a wall time or a comparison has to hold across hosts or repositories,
measure it through crypto's [ICMS](https://github.com/aburan28/crypto/blob/main/docs/ic/measurement/README.md)
([crypto#1177](https://github.com/aburan28/crypto/pull/1177)).
It runs one ic-bench cell per run, pinned to a reserved core with the frozen
calibration, and records the host and the isolation level the run earned. It
refuses a comparison whose unit, window, reference, stop rule or workload
differ. See [Running a cell under ICMS](experiments/ic-bench/README.md#running-a-cell-under-icms),
which also lists how this harness's figures differ from crypto's and
crypto-autoresearcher's.

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

## Hardware and placement for empirical benchmarks

For every performance or memory comparison, save a machine-readable hardware
and execution manifest with the run receipt. Record the CPU vendor, exact
reported model and generation or microarchitecture when independently known,
architecture, exposed cores/threads/sockets, cache topology, kernel and OS,
virtualization/container status, and CPU and memory cgroup limits. Record the
physical memory technology (for example DDR4 or DDR5), speed, and channel
configuration only when the host exposes verifiable evidence; otherwise write
`unknown`, especially in a VM. Do not infer DIMM type from a CPU model.

Record allowed CPUs and NUMA memory nodes, the selected CPU affinity and
memory policy, and observed page placement for the measured process. On a
multi-node host, choose a CPU and its local memory node together, first-touch
the working set under that policy, and verify the placement. If only one node
is exposed, say so and do not claim a NUMA locality comparison or host-level
isolation. CPU affinity restricts the benchmark process's placement; it does
not reserve a core from other processes. Record any CPU throttling and relevant
co-runners where observable.

Pair variants on the same host, core/node policy, inputs, limits and warmup
policy. Report process CPU time and wall time separately, along with peak RSS,
operation counts, rank progress, and algorithm-specific work such as row
fill-in. Include repeated paired runs and variability for timing claims;
never treat one elapsed-time result alone as evidence of a solver speedup.
Keep source and input hashes and record censored, timed-out, or memory-limited
runs as such.

## CPU performance isolation gate

Treat CPU timing ratios from a contended or unverified host as exploratory.
Promote a new CPU wall-time speedup claim only with a receipt from the
[isolated benchmark service](docs/ISOLATED_BENCHMARKS.md), or an equivalent
auditable host-level isolation record. The record must identify the physical
CPU model, core and SMT topology, NUMA node, exclusive CPU partition,
execution CPU affinity, memory policy, fixed frequency, IRQ routing, CPU
quota, code and workload hashes, paired run order, raw failures, throttling,
steal time, interrupts, and correctness. A container's visible affinity mask
does not establish host-wide isolation. If the isolation preflight or any
noise gate fails, preserve the row and keep aggregate speedup unknown.
Re-evaluate earlier measurements lacking this evidence before citing them as
controlled speedup results. Correctness runs and algorithmic diagnostics may
still run on ordinary hosts when labeled accordingly.

## Remote compute

A cloud-agent VM has 4 CPUs, 15 GB and no GPU. Run bigger work, such as
multi-core sweeps, Sage/F4/SAT grids, long test suites or CUDA, with the
tools in [`cloud/`](cloud/README.md). Both run the command on a copy of the
working tree and copy the results back into the checkout:

- `cloud/modal_run.py run [--image cpu|cuda|sage] [--cpu N] [--memory GB]
  [--gpu TYPE] [--shards K] [--out PATH | --changed] [--detach] -- CMD` runs
  on Modal and is billed per second.
- `cloud/fleet.py run rp-cpu-1|rp-gpu-1 [--out PATH | --changed] -- CMD`
  runs on the Runpod pods; `cloud/fleet.py status` and `up NAME` show and
  start them.

If `FLEET_WORKER_NAME` is set, you are already on a fleet pod: run locally,
up to `$FLEET_CPUS` wide. Stop or kill whatever you start, never write
credentials into the tree, and copy the hardware from each shard's
`status.json` into the run record.
