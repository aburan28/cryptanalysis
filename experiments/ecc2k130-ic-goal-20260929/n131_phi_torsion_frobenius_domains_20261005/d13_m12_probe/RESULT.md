# Q20261006081500: N131 d13/m12 public-target relation proposal

**Measured result:** the accepted-seed public-target query reached its frozen
600-second wall cap. It charged 599.749 seconds to one supplied target,
including 595.376 seconds of CryptoMiniSat search, and stayed below the
4-GiB combined-RSS limit with a conservative peak of 1,808,089,088 bytes.
The [independent Sage audit](public_q_runs/d13_m12_20261009T221148Z/independent_sage_replay.json)
verified the saved run's curve, workload, protocol, formula, and resource
identity and recorded zero models and zero relations. The proposal ID is
`Q20261006081500`; its candidate and run IDs remain null because this is a
first-relation diagnostic. The exact formula, planted controls, and
independent full-base Sage audit pass.

The write-once sequence retains both producer failures and the measured
query. The [first run](public_q_runs/d13_m12_20261009T220450Z/result.json)
stopped before SAT when the same target coordinates were compared as integer
geometry values and decimal workload strings. Version 3 corrected that
comparison; its [solver output](public_q_runs/d13_m12_20261009T220843Z/attempts/model_01/cryptominisat.stderr.txt)
shows CryptoMiniSat rejected seed `202610061312` at argument parsing, although
the v3 runner labeled the record `timeout`. Version 4 froze accepted seed
`2026100613` and classifies unexplained solver exits separately from resource
stops. The earlier source and results remain unchanged.

| Frozen execution | Terminal status | Target query (s) | Solver (s) | Conservative peak RSS | Models / verified relations |
| --- | --- | ---: | ---: | ---: | ---: |
| [Original](public_q_runs/d13_m12_20261009T220450Z/result.json) | `producer_failure`, coordinate type check | 0.000287 | 0 | Not measured | 0 / 0 |
| [V3](public_q_runs/d13_m12_20261009T220843Z/result.json) | `producer_solver_argument_failure` from raw stderr; runner says `timeout` | 0.991 | 0.311 | 219,168,768 B | 0 / 0 |
| [V4](public_q_runs/d13_m12_20261009T221148Z/result.json) | `timeout`, parent wall guard | 4.373 | 595.376 | 1,808,089,088 B | 0 / 0 |

V4's target-dependent charged total is 599.749 seconds; its query and solver
phase entries sum to that value. The solver was terminated by the parent wall
guard (`exit_code=-15`, `stop_reason=parent_timeout`), with zero SAT status or
model lines in the retained raw output. This is a zero-yield observation for
the exact formula and target under the stated cap, not a yield estimate for
other targets or methods. The next method gate is a target-coupled six-pair
solver that first passes an ordinary N41 control, measures pruning while at
least two pair domains remain unchosen, and avoids a quadratic pair-output
table. A source-bound 600-second/4-GiB N131 projection precedes a new public-Q
run; every returned model requires the saved-XCNF and independent Sage group
replay.

The controlled change is the phi subspace and summand count on the same
degree-131 challenge curve and frozen one-point official-Q workload. The
[exact geometry](../m12_d13_static/d13_exact_geometry_v1.json) has 4,134
valid signed point choices per position, 1,083,108 actual nonidentity
subgroup points before sign/Frobenius folding, and 4,134 folded columns.
The 12 conjugate position domains are disjoint except at zero.

| Static variant | Summands | Dimension | Folded columns | XCNF variables | Clauses | Native XOR rows | XCNF bytes | Uniform-sum expected signed tuples across four cofactor endpoints |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sparse d9/m16 | 16 | 9 | 274 | 297,827 | 232,553 | 220,253 | 11,274,405 | 97,189.5 |
| Sparse d10/m15 | 15 | 10 | 532 | 282,598 | 225,092 | 208,783 | 10,879,816 | 3,726,104.1 |
| This d13/m12 probe | 12 | 13 | 4,134 | 232,244 | 228,629 | 171,278 | 11,202,092 | 149,946,445.4 |

The last column is a **prediction under uniform ordered signed tuple sums**,
not a fixed-Q relation count, SAT model count, yield measurement, or running
time. Against sparse d9/m16, d13/m12 has 65,583 fewer variables and 48,975
fewer native XOR rows while its serialized formula is only 72,313 bytes
smaller. The larger base also raises the final relation-matrix dimension;
formula size alone cannot determine end-to-end IC cost.

The exact d9/m16 and d10/m15 configurations in this static comparison are
`IC1N131Ckb1fb71788PDP16satRCdirectLAgaussTDdirectISO0h758917c155b2`
and `IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h35d801e69db9`.
Both the factor base and summand count change across rows; no measured
online-speed comparison is implied.

The [source-bound formula receipt](d13_m12_formula_and_planted_control_v1.json)
records the exact public-Q XCNF SHA-256 and a separate planted synthetic
target. The generator checked the planted Boolean assignment and exact model
decoder. The [witness](d13_planted_witness_v1.json) was then replayed with
the repository's checked Sage launcher. The [independent Sage receipt](sage_d13_planted_relation_audit_v1.json)
verifies all 12 leaf points, 10 partial sums, the four endpoint lifts, and
two signed folded group replays. This replay checks the witness orbits, not
the complete base. The [runtime receipt](sage_runtime_info.json) was saved
before these local Sage jobs.

The independent installed-Sage full-base audit now passes. It independently
verified the 13-dimensional Frobenius domains and their 1,073,022-coordinate
union, the official-Q embedding and four-endpoint fiber, all 4,134 valid
selectors, all 131-step signed Frobenius orbits, and the exact digest of
1,083,108 usable subgroup points before folding into 4,134 columns. See
[sage_d13_full_base_audit_v1.json](sage_d13_full_base_audit_v1.json) and its
checked-runtime receipt
[sage_runtime_info_d13_full_base_audit_20261006T082340Z.json](sage_runtime_info_d13_full_base_audit_20261006T082340Z.json).
This closed the complete-base correctness gap before the public-target runs
reported above. The full candidate's factor-log preparation and target
recovery remain downstream of the ordinary-relation gate.

The [d13 full-pipeline adapter check](../m12_d13_full_pipeline/adapter_formula_equivalence_v1.json)
also reproduces the saved official-Q XCNF byte-for-byte through the reusable
runtime relation-formula path: 232,244 variables, 228,629 clauses, 171,278
native XOR rows, and 11,202,092 bytes. This verifies that the exact d13
encoder can be wired through the existing relation and row-normalization
helpers. The adapter is not yet a complete frozen runner, so `candidate_id`
and `run_id` remain null.

The [frozen first-relation protocol](public_q_first_relation_protocol_v2.json)
binds the one supplied Q, exact formula, source files, CryptoMiniSat binary,
600-second limit, 4-GiB combined-memory limit, and predecessor gates. Its
partial-query clock starts before selecting and checking Q's cofactor fiber;
it also charges formula construction, every SAT attempt, and local row checks.
The [checked-Sage preflight](preflights/d13_m12_20261006T083203Z.json)
returned `WAIT_FOR_R3_DRAIN` without creating a run directory or launching a
solver. A [gate control](preflight_gate_control_v2.json) exercised the live
wait, a synthetic verified-R3 stop, an unfinished-d10 wait, and a synthetic
terminal-unsolved admission. The [independent Sage auditor](audit_public_q_first_relation.py)
will verify saved CryptoMiniSat output against every CNF/XOR record and
replay leaf membership, the partial chain, folded representative membership,
and the group equation. Its [planted and tamper control](sage_public_q_auditor_planted_control_v4.json)
passed both signs and rejected a changed leaf and folded coefficient.
The [saved-XCNF control](saved_xcnf_planted_control_v1.json) separately
verified all 401,375 records of a complete planted d13/m12 formula and
rejected a changed pinned leaf bit using the independent XCNF parser.
These controls do not estimate natural relation yield.

The checked-Sage [continuation watcher](continue_after_d10.py) was started
after a one-shot gate check. At 08:35 UTC its [state](continuation/state.json)
was `WAIT_FOR_R3_DRAIN` with process identity recorded and no d13 run
directory. The subsequent exact d10 v3 process-loss
[audit](../../n131_d10_v3_external_interruption_20261009/result.json)
and terminal d10 v1 continuation receipt cleared the v4 probe's frozen
predecessor gate. The first public-Q run sequence is reported above.

Before constructing a full d13 candidate, account for its 4,134 folded
columns: a complete logarithm precomputation needs at least 4,134 independent
equations. The frozen d10 runner's cap of 256 precomputation targets and four
model attempts per target could produce at most 1,024 rows, so that policy
cannot be copied for d13. The d13 pipeline now has a separate sparse
forward-elimination/back-substitution module with correctness controls over
the subgroup modulus; randomized small systems, known-log replay, dependent
rows, and inconsistent rows pass. Its large-matrix time and memory remain
unmeasured, and this module does not create a candidate ID or prove natural
relation yield. A full d13 candidate must freeze a larger target-independent
relation budget and account for sparse matrix cost before a one-target online
run.

## Full-width exact FLINT rank control (2026-10-06 09:38 UTC)

The completed [synthetic 4,134-column sparse-rank control](../m12_d13_full_pipeline/flint_relation_rank_fullwidth_v1.json)
recovered its planted 4,134-entry log vector over the ECC2K-130 prime
subgroup modulus. It inserted 4,166 generated 12-sparse equations plus one
consistent duplicate (4,167 total), reached rank 4,134, replayed every
equation, and gave the duplicate zero rank gain. Elimination took
918,192,810,834 ns (918.19 s) with a reported process peak RSS of
356,286,464 bytes; final equation replay took 8,465,584 ns.

The accompanying [build and host provenance](../m12_d13_full_pipeline/flint_relation_rank_fullwidth_provenance_v1.json)
binds the test receipt, C++ source, solver binary, FLINT/GMP libraries,
compiler, and linked libraries. CPU isolation was not established, and the
diagnostic ran while the unrelated one-thread R3 solver remained active, so
the time is exploratory. This establishes full-width exact-solver correctness
and a practical memory footprint for synthetic rows. It does not establish
natural d13 relation density or yield, completed factor logs, a DLP, online
time, or a speedup. The d13 probe and full candidate remain behind the
existing R3/d10 gates.

The next pipeline gate is still one naturally sampled ordinary d13/m12 row for
the frozen public Q after those predecessors terminate. Once its row-yield
distribution is measured, use this full-width result to bound the FLINT matrix
stage; do not extrapolate the synthetic 12-sparse row pattern into an IC
throughput claim.

## Frozen full-pipeline single-target candidate (2026-10-06 10:07 UTC)

The complete d13/m12 path now has an immutable candidate manifest and run
protocol:
[`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h44e0b7f66da0`](../m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json).
It binds the exact 1,083,108-point factor base, 4,134 folded columns,
twelve-summand Boolean XCNF/CryptoMiniSat decomposition, direct relation
collection and target handling, and exact FLINT final relation-matrix solver.
The independent one-target workload ID is `3c1992b7c92f` (the supplied public
ECC2K-130 Q).

The protocol allows at most 8,192 target-independent preparation queries,
each a singleton random `aG` query capped at 600 seconds and four SAT models.
Preparation stops only after 4,134 independent equations yield factor logs
that replay on the curve, or records the terminal failure/limit. It then
attempts exactly one online DLP for the supplied Q. The online clock starts
with target-dependent fiber/formula work after reusable logs are verified;
launch, input loading, factor-base construction, and log preparation are
outside that interval. The one-thread memory envelope is 4 GiB. Compressed
solver artifacts have a 4-GiB run budget; every query retains its status and
uncompressed artifact hashes after the archive budget is reached.

The checked-Sage candidate preflight at 10:11 UTC verified all frozen source,
evidence, candidate, curve, and workload digests, then returned
`WAIT_FOR_R3_DRAIN`. Its [receipt](../m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T101125Z.json)
confirms `target_count=1`, `batch=false`, and `solver_launched=false`. R3 is
still active; d10 and the public-Q probe remain gated. This is a fully specified
candidate protocol, not a natural relation, completed precomputation, DLP, rho
comparison, or speedup measurement. The candidate ID is frozen, while its run
ID remains null until the gate opens and a run actually starts. The runner now
checks the `PDP12sat`, `RCdirect`, `LAgauss`, `TDdirect`, and `ISO0` stage-code
mapping and enforces the same conservative 4-GiB memory envelope over factor-
base setup, each SAT query, and each parent-plus-FLINT matrix worker.

The 10:14 UTC [R3 sample](../continuation_20261006/r3_live_resource_sample_20261006T101430Z.json)
still matched both process identities, showed recent solver-log growth, and
reported rank `0/14` with no terminal result. D10, the d13 diagnostic, and the
full candidate remain at `WAIT_FOR_R3_DRAIN`.

## Full candidate protocol refresh (2026-10-06 10:45 UTC)

The full d13/m12 candidate was refrozen after adding stage-level FLINT
provenance, a full-run independent Sage auditor, and a persistent continuation
controller. Its current ID is
[`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0h963f931502c1`](../m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json),
on the same single supplied-Q workload. The checked-Sage
[preflight](../m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T104458Z.json)
passed the freeze-integrity checks and returned `WAIT_FOR_R3_DRAIN`, with
`target_count=1`, `batch=false`, and no SAT launch. The persistent
[continuation state](../m12_d13_full_pipeline/candidate_continuation/state.json)
is also waiting for the d10 and d13 gates to reach terminal states.

The new [v2 full-width matrix control](../m12_d13_full_pipeline/flint_relation_rank_fullwidth_v2.json)
passes exact rank and known-log replay at 4,134 columns. It measures only a
synthetic matrix: 4,167 planted 12-sparse rows, 925.05 seconds of elimination,
and 357,335,040 bytes peak RSS. Host isolation was not established, so no
speedup or natural-query cost follows from this diagnostic. The latest
[R3 sample](../continuation_20261006/r3_live_resource_sample_20261006T104216Z.json)
shows active solver work and new log bytes, but rank remains `0/14` with no
terminal result. No ordinary d13 relation, factor logs, or one-target DLP is
available yet.

## Online timer boundary correction (2026-10-06 11:05 UTC)

Review found SAT artifact compression occurring before the recovered scalar
was checked, which charged diagnostic file work to the online interval. The
runner now stops the primary online timer after the target scalar is recovered
and replayed, then archives SAT artifacts outside that interval and records the
archive duration/status separately. A compression failure remains a diagnostic
record and no longer invalidates a scalar already verified against Q. The
independent Sage auditor checks that archival is marked excluded from online
time. The candidate was refrozen as
[`IC1N131Ckb1fb1083108PDP12satRCdirectLAgaussTDdirectISO0ha088b3d8e4a0`](../m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json).
The checked-Sage preflight
[`d13_m12_20261006T110556Z.json`](../m12_d13_full_pipeline/single_target_preflights/d13_m12_20261006T110556Z.json)
returns `WAIT_FOR_R3_DRAIN`, `target_count=1`, `batch=false`, and
`solver_launched=false`. The v5 rho identity audit passes all 18 checks for
this updated candidate and the same supplied Q. No SAT run launched.

## Explicit one-target controller state (2026-10-06 13:27 UTC)

The continuation watcher previously wrote `target_count=1` but omitted the
protocol's explicit `batch=false` value from its state snapshot. Its controller
now rejects any protocol that does not specify exactly one target and
`batch=false`, and persists `batch=false` in both the top-level state and the
last-preflight record. The updated script passed checked-Sage syntax
validation. I restarted only the idle watcher after identity-checking its PID;
the new state is `WAIT_FOR_R3_DRAIN`, `target_count=1`, `batch=false`, and
`solver_launched=false`. The active R3 solver was not signaled. The startup
runtime receipt is
[saved here](continuation/runtime_receipts/sage_runtime_info_batch_state_fix_20261006T1326Z.json).
