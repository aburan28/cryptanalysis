# Exact cached-prefix point replay for cutset queries

The original independent point replay lifts every selected factor-base
abscissa and recomputes every signed prefix sum for each returned witness.
This experiment precomputes the two signs of each liftable seven-bit
abscissa and every finite two-point sum. Both are target-independent curve
geometry. Every target still receives fresh packed S3 coefficients, native
cutset solves, original field/static ANF checks, and a fresh extension of
the cached pair states through summands three to `m`. No target result or
complete witness answer is cached.

For a fixed selected abscissa tuple, the pair table contains exactly the
finite sums of all signed choices of its first two points. Inductively,
after processing summand `j`, the state set contains exactly the finite sums
of the first `j` choices whose prefixes of lengths `2..j` were all finite.
Extending every state by both signs and dropping infinity proves the
invariant. The final step returns true exactly when a finite final sum has
the target abscissa. This is the same predicate as the reference replay's
Cartesian-product enumeration. Deduplication is sound because later group
addition depends only on the partial point. The pair table uses O(B_x^2)
entries for `B_x` liftable abscissae and is limited here to GF(2^9), curve
`b=1`, seven-bit coordinates, and four or five summands.

Freeze the two seed-1, ell-7 cutset cases, their two or four static branches,
the 24-variable bag and 200,000,000-state per-branch limits. Bind the
predecessor [packed-cutset exact report](../groebner-f6-cutset-packed-20261009/evidence/complete/report.json.gz)
by its SHA-256
`fd92b8ced02d60e3b3166f76f47a0759be1da148c192d22974bba2f823169f29`.
Use its independently enumerated branch-restricted target sets as the
status comparator. For optimized and UBSan builds and all 512 target
abscissae, run both replay arms over the same native layouts and packed
coefficient buffer. Require equal native branch statuses and assignments,
equal point-replay predicates, original S3/static equation checks, and
independent reference point replay again outside the timed interval for
every SAT branch. Also compare the replay plan with the original verifier
on 1,024 deterministic random assignment/target pairs per case, an
all-zero-abscissa infinity-prefix control, and an unliftable-abscissa
control. Preserve failures and cap statuses. Acceptance requires 4,096
complete primary queries and 12,288 native branch queries.

For complete-query timing, use the optimized build, three target warmups
per arm (`0`, `1`, `161`), then three 512-target passes per case. Alternate
reference/planned order by target and repetition. The online interval
starts before fresh target coefficients and ends after all native branches,
static/original S3 checks, and point replay. Pair 6,144 complete query rows
and retain all 18,432 native branch rows. Keep pair-cache setup outside
the target-dependent interval and report its time and size separately.
Resample target abscissae as clusters for the exploratory paired interval;
a controlled CPU speedup requires an isolated-host receipt.

Run the source-bound grouped-factor build chain in
`.github/workflows/groebner-f6-replay-plan.yml`, then the validator from a
clean committed checkout:

```sh
python3 experiments/groebner-f6-replay-plan-20261009/validate.py \
  --output /absolute/path/to/new-evidence-directory
```
