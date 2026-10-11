# Fresh exact fixed-block symmetry

This experimental producer checks whether swapping the two equal halves of
its fixed-variable block leaves every specialized residual coefficient
unchanged. When that exact check succeeds, it solves only the earlier branch
of each swapped pair, then expands all roots and certificates. The complete
query still uses round34's unchanged independent checker. This reduces
repeated branch elimination; it is not a general F4/F5 replacement or a new
asymptotic complexity result.

## Applicability and correctness

For a split with `x = 2k` fixed Boolean variables and `y` residual variables,
write a fixed branch as `(a,b)` with `k` bits each. After fresh packed ANF
specialization, compare every residual coefficient of `F(a,b,z)` and
`F(b,a,z)`. All duplicate terms have already cancelled by XOR. No sampled
check or assumption about the target family is used. A mismatch disables the
optimization for the entire query. Odd `x` uses the unchanged full solver.

For equality on every pair, the earlier branch is a representative. There
are `2^k * (2^k + 1) / 2` representatives, including the diagonal exactly
once. Process original branch IDs in ascending order. Copy each constant
contradiction prefix and, if present, append a complete affine identity with
the alias branch ID. Copy actual roots with the alias fixed bits and the same
residual bits. Sort the complete root set before unchanged basis construction;
no assumption about how the reduced basis permutes is needed.

The independent round34 checker receives the full original ANF and the full
expanded proof. It has no symmetry flag or representative map. It reconstructs
every claimed identity from the original equations and enumerates every
uncertified branch over its original residual variables. Its exact root count
and Boolean basis certificate therefore remain independent of the producer's
symmetry decision. If proof-copy limits are reached, omitted identities cause
normal exact checker enumeration or an explicit inconclusive result.

Reused data consist of target-independent layouts and allocated buffers. Each
query builds fresh coefficients, checks symmetry, solves, expands, and
certifies. Alternating symmetric/asymmetric queries exercise reset behavior.
Partial roots and proofs are never returned as a complete answer.

## Work, memory, and device accounting

The scan and expansion are included in evaluation time; their separate timers
are nested diagnostics and must not be added twice. Branch and consistency
counts retain logical full-branch semantics. Elimination, multiplier rows,
XORs, lifted candidates, and fallback assignments count actual representative
work. Direct affine proofs and copied affine proofs are recorded separately.
Two reusable offset arrays add `(2 * branches + 1) * 4` bytes for even `x`.
They are allocated even when the fresh input proves asymmetric.

The limits remain round34's: 64 MiB per specialization table, 64 MiB proof
storage, 67,108,864 multiplier rows plus pivot XORs per query, 65,536 per
branch, 4,194,304 enumeration assignments, 256 complete roots, and 1,000,000
basis-check work units. Alias copies additionally have a 64 MiB word budget.
The test build with zero copy budget exercises exact checker fallback.

Metal remains opt-in and uses the existing kernel for at most 31 features
and 32 equations. **That kernel still eliminates every fixed branch**, even
when the host later consumes representatives only. The report records this
full GPU work. The 24/27-variable requested Metal cases use explicit CPU shape
fallback. CPU remains the default; no CUDA or other-device claim is made.

## Measurement and reproduction

Use a normal Python interpreter; this code does not import Sage. Build rounds
20, 23, 31, 32, 33, 34, then 35 with their respective `build.py`. On macOS,
append `--metal` to rounds31 through35 to enable requested Metal controls.

```sh
python experiments/groebner-perf-20260924/round35/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round35 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round35/measure_symmetry.py --correctness-only --repetitions 2 --output correctness.json.gz
python experiments/groebner-perf-20260924/round35/measure_symmetry.py --correctness-only --large-controls --repetitions 2 --output wide-correctness.json.gz
python experiments/groebner-perf-20260924/round35/audit_symmetry.py wide-correctness.json.gz
```

Set `QUADRATIC_TEST_METAL=1` for Metal tests and append `--metal` to measurement
commands. CI rebuilds on native Linux and macOS runners, runs the exact tests,
and independently audits fresh and retained evidence. Native library hashes,
source snapshots, build flags, device execution, and raw proof journals bind
every measured result. The offline Python work model uses original ANF
monomials and Python integers, not native tables or pivots. This instrumentation
check is separate from the mathematical completeness check.

The measured boundary includes public-point validation, fresh packed descent,
solving, proof generation/copy/hash, independent certification, original
equation checks, curve replay, and reference-ANF evaluation. Fixed setup and
additional offline auditing are recorded separately. Small controls compare
six CPU and five requested Metal arms. Wide controls compare the unchanged
round33 expanded-enumeration baseline, round34 affine multipliers, and this
producer, each on CPU and requested Metal. Direct round33-to-round35 pairing
is measured; speedup ratios from separate experiments are not multiplied.

Performance attempts omit `--correctness-only`. The predeclared trials use 31
measured repetitions plus one warmup for small controls and seven plus one
warmup for the nine 21/24/27-variable controls, repeated independently. Arms
are shuffled within each repetition. Initial, every paired-group start/end,
and final one-minute load must be at most one per logical CPU. This admission
rule is necessary but cannot prove an uncontended host. Retain nonadmissions,
interruptions, failures, and load-ineligible runs. Paired bootstrap intervals
apply to these fixtures, not unseen targets. A GPU win requires actual GPU
execution and beating the fastest paired CPU arm over the complete query.

## Research scope and next steps

The structural gain is a finite symmetry factor, approaching two for the
representative branch work. Specialization, proof output, and independent
verification still cover every branch. There is no asymptotic improvement
claim. Low-degree multiplier certificates remain the established technique
implemented in round34, with its counterexample that requires exact fallback.

The next experiments should use phase evidence to choose between compact GPU
representative scheduling, GPU affine-row elimination, and reducing the cost
of fresh specialization and independent checking. Swapping a fixed block with
the residual block requires a separate domain and certificate argument; it is
not covered by this two-fixed-block proof. An F6 proposal needs explicit
applicability, difficult counterexamples, and a complexity argument before
being called a novel asymptotically faster algorithm.

These frozen planted inputs are PDP correctness and component-performance
controls. `candidate_id`, `IC_online_ms`, and `rho_online_ms` stay null. Natural
relation yield and the full same-point single-target IC/rho comparison need
separate complete pipeline manifests and verified recovery measurements.

Measured outcomes and paired intervals are in [RESULTS.md](RESULTS.md). The
next implementation and research gates are in [NEXT.md](NEXT.md).
