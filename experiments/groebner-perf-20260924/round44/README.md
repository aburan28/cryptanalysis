# Partial-affine certificates in complete Boolean queries

This experiment integrates round43's residual proof idea with round42's
quadratic query implementation. At a rank-deficient affine projection, the
producer can search the remaining free variables and carry witnesses for the
affine constraints into the independent checker. Selecting this round44 module
opts into the experiment. Existing solver dispatch is unchanged, and
`partial=False` retains the previous producer path for an explicit ablation.

For `y` residual variables and verified affine rank `r`, the search contains
`2**(y-r)` assignments. The constraints are equation-row combinations, so every
original root satisfies them. The checker reconstructs those combinations
from independently decoded original coefficients, rejects nonlinear
consequences, recomputes rank and pivots, and evaluates the original equations
on every remaining assignment. It never trusts producer rank or root counts.
The existing complete-root, reduced-basis and Boolean quotient-dimension
checks still apply. This does not establish a general asymptotic improvement.

The tagged wire format and charged failure behavior are specified in
[PROTOCOL.md](PROTOCOL.md). Old contradiction records remain accepted; old
checkers reject the new tag. Missing or all-zero witnesses cause complete
enumeration. A producer attempt commits neither roots nor a proof until its
entire search succeeds. Assignment, work, root, table and proof limits remain
bounded. Inconclusive results never become partial bases.

## Reproduce correctness

Use Python 3.12 or later and a native C++17 compiler. No Sage process is used.
Build the dependencies with the local compiler:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 42; do
  python "experiments/groebner-perf-20260924/round${version}/build.py"
done
python experiments/groebner-perf-20260924/round44/build.py
(cd experiments/groebner-perf-20260924/round44 && python -m unittest -v test_partial.py test_tagged_edges.py)
python experiments/groebner-perf-20260924/round44/validate_native.py --output partial-query-evidence/correctness.json.gz
python experiments/groebner-perf-20260924/round44/audit_queries.py --input partial-query-evidence/correctness.json.gz --output partial-query-evidence/independent-audit.json
```

On macOS, add `--metal` to both round42 and round44 builds and to validation.
Set `QUADRATIC_TEST_METAL=1` for the unit suite only when a Metal device is
available. The validator records unavailable requested devices explicitly.
Allocation, shader and execution errors fail validation. Equation counts above
32 use the recorded CPU fallback. The GPU shader is unchanged from round42;
there is no CUDA, OpenCL or HIP coverage claim.

The frozen round42 corpus has 6,001 systems; each runs with partial certificates
enabled and disabled on every selected backend/build. Disabled successful
outputs must match round42's roots, reduced bases and exact proof bytes.
Enabled outputs must preserve complete roots and reduced bases. An independent
Python reference checks each proof. The 18 frozen complete-query fixtures also
run in both configurations with fresh equations and signed curve replay, then
undergo a separate offline original-ANF and reduced-basis audit.

Ten additional test groups exercise forced partial ranks through ten
residual variables, equation masks through 128 bits, asymmetric fresh inputs,
rank-zero/full-rank systems, malformed proofs, missing/zero/dependent
witnesses, old-checker rejection, symmetry-copy exhaustion, result rollback
after roots have been found, global budgets and concurrent context reuse.
Externally constructed full-rank and inconsistent tagged proofs are checked
independently of the producer's narrower partial-rank emission policy.
Native code is rebuilt on each hosted Linux x86-64 and macOS ARM64 runner;
actual binaries and source receipts are retained by the dedicated workflow.

## Evidence and interpretation

Physical M4 Pro optimized CPU, UBSan CPU and Metal validation passes 36,006
system runs: 35,898 verified and 108 expected root-limit outcomes. All 108
complete-query runs pass the native independent checker and unchanged equation
and signed-curve replay. Each backend has 854 small-system inputs that exercise
the new partial path. The separate complete-query Python audit passes all 108
records and 47 distinct proofs. Both external-certificate boundary tests pass
on optimized and UBSan CPU builds. Compact source-bound evidence is retained
in [evidence/physical-m4-correctness.json.gz](evidence/physical-m4-correctness.json.gz).
The [packaging binding](evidence/packaging-binding.json) records one removed
blank line in a Python wrapper with an identical parsed syntax tree and the
two additional external-certificate tests. CI validates the final sources.

The counters show a tradeoff, not a measured speedup. On the three 27-variable
fixtures, partial handling replaces 12,981–13,293 representative residual
attempts. Macaulay row XOR counts fall from 6,953,829–7,128,112 to
21,177–21,520. However, independent checker candidate evaluations increase
from 3,072 to 56,314–57,540, and witness reconstruction/rank work must be paid.
On the 24-variable fixtures, only 15–16 representatives take the new path.
These counts cannot be converted directly to wall-time gains.

No timing run is part of this correctness package. A subsequent experiment
must freeze all comparators, use complete query timing, retain rejected trials
and failures, and obtain repeated qualifying measurements before changing
dispatch. Original proof bytes and platform/build identities are retained in
the local evidence and CI artifacts; no target answer is cached in the timed
implementation. Python reference caching is restricted to the offline audit.

This remains a bounded planted polynomial/PDP diagnostic with
`candidate_id: null` and `online_speedup: null`. It establishes neither natural
relation yield nor a complete IC result, a general high-regularity F4/F5
ranking, or an asymptotic “F6” claim. Full 30-variable tables still exceed the
unchanged memory guard; coefficient tiling is a separate next experiment.
