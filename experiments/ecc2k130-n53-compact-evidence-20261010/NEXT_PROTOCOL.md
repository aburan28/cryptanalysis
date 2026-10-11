# Fixed-base n53 rank-restart comparison: preregistration for a future run

The next implementation experiment will test whether bounded restarts reduce
the compact S3-root rank collector's complete probe cost at the existing
**n53 K220, B=23,320** source-curve base. The 220-row archived rank trace
has p90 198,997 probes and a 34.8261% top-decile probe share. These figures
select restart caps for a new test; they are retrospective pilot evidence,
not a measured restart benefit.

1. Preserve curve, generator, subgroup, exact factor-base point digest
   `7af2460c8b5a2c29f9d1aa7fefecbcde3a6ce761293d0dab0cecfc3bc980b973`,
   the archived development public point
   `[7960849849661793,7443722527872608]`, K220, four-summand S3-root
   solver, index construction, final LA and direct target-recovery policy.
   Give each changed rank collector its own complete candidate manifest;
   retain `candidate_id: null` until that manifest and the run are complete.
2. Implement one explicit rank-query change in `crypto`: after **200,000**
   or **400,000** support probes on a rank attempt, abandon that attempt and
   draw the next scalar from the same recorded deterministic stream. Do not
   reuse a partial witness. Count its spent probes, query construction and
   elapsed PDP cost. The unbounded collector is the control. Keep the first
   pivotless-column target rule unchanged so the only planned algorithmic
   variable is the restart cap.
3. On the published development point, run both caps and the unbounded
   control on rank seeds `530053`, `530054`, and `530055`. Record every
   attempted target, spent/aborted probes, verified relation, pivot/rank
   transition, failure, setup phase, and target scalar replay. This pilot
   chooses one cap by lowest median **complete cold** cost among variants
   that finish full rank and recover the target in every pilot cell. Preserve
   all caps and seed failures. A selected cap with lower probe count but
   higher cold cost remains a negative result.
4. Before a new held-out point or timed result, commit/push the exact
   producer source, build inputs and this protocol, plus candidate/workload
   manifests and the input-generation rule `hash:53261307` under the same
   public hash-to-curve/cofactor procedure as the parent panel. The six
   **independent** rank seeds are `531053` through `531058`, and paired rho
   seeds are `530153` through `530158`, in order. Use the resulting one
   previously unseen public point for both collectors and each rho arm.
   If the generated point duplicates a committed prior input, retain that
   eligibility failure and stop without replacing the seed. The scalar is a
   verifier-only sidecar; the IC process receives only Q. Pair capped and
   unbounded runs by rank seed, target, base digest, resource cap and host.
5. Charge base/index build, every successful and aborted rank attempt,
   relation checking, matrix/final LA and target recovery to supplementary
   cold cost. Measure the five exclusive target-online phases separately,
   then compare each verified IC arm with rho on the same point. Retain raw
   JSONL, stderr, exits, timeout/OOM, peak RSS, exact source/binary/input
   hashes and independent replay of every rank row and recovered scalar.
   Use one process/thread per arm, a 60-second wall cap and 16-GiB observed
   RSS cap for both pilot and held-out cells; do not replace failed seeds.
   The CPU host must pass the repository's isolation gate before a controlled
   wall-time claim; otherwise keep wall ratios exploratory.

The advancement gate is full-rank and verified target recovery on all six
held-out seeds with unchanged B/base digest, no missing phase, and a median
paired **total rank-probe** reduction of at least 15% **without an increase
in paired complete cold cost**. This is an engineering selection threshold,
not a security or asymptotic claim. If the gate fails, retain the complete
rows and investigate per-probe arithmetic or a different index policy.
Any degree-263 source/descendant comparison then remains a separate
equal-useful-base, same-target transport experiment with its route costs.
