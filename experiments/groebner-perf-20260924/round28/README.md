# Conditional solving inside complete single-target IC

This opt-in experiment compares three complete pipelines on the same exact
curve, factor base, resource envelope and public target:

| Arm | Collection and target decomposition | Independent basis checker |
| --- | --- | --- |
| three-eval | three-summand Boolean evaluation/interpolation | frozen round26 selection: packed at ell=3, sparse at ell=6 |
| two-eval | two-summand Boolean evaluation/interpolation | round23 sparse exact proof |
| two-conditional | two-summand conditional linear solving/interpolation | round27 independent branch-count and exact staircase proof |

The two two-summand arms isolate the solver/checker change. Comparing either
with three-eval changes the mathematical decomposition strategy: both relation
yield and the number of attempts may change. All candidates use independent
Euclidean field inversion for validation and scalar replay, with the same
arithmetic charged to the paired rho control. The complete pipeline is CPU-only.

## Target independence and accounting

The prepared contexts receive no public target or fixture scalar. Each has its
own relation collection, matrix rank, verified column logs and native workspace.
The two-summand workspace is installed inside the existing precompute ledger,
before any relation query. Construction and disposal of the inherited unused
three-summand workspace are included in preparation. The existing collection,
factor-base projection, first-usable target policy and recovery code are reused.

The external fixture excludes the union of every arm's preparation query points,
their negatives, known projected base columns and generator. Each arm's excluded
set digest is retained separately. This changes the workload identity whenever
the exclusion set changes; it does not silently reuse the earlier workload ID.
Fresh contexts repeat the same declared collection stream and verify their own
exclusion digest before receiving the common public target. No target answer is
cached. Fixture generation and reusable preparation stay outside online timing.

Each measured group has three independently prepared IC solves and one
same-point rho solve, in randomized order. The rho reference is one solve of
that public point, with one worker and no cross-target collision state. Each IC
receipt pairs with this same reference. Repetitions are independent single-target
experiments, not batch throughput or shared-preparation amortization.

The online interval starts with public-point validation and stops after
independent scalar recovery. Five exclusive phases sum exactly to the interval:
target query, PDP, relation checking, descent and recovery checking. All failed
attempts, rejected lifts, root/proof limits and fallback work remain charged.
Setup, preparation status mix, useful rows, rank, memory and log replay remain
separate stage records. Unmetered operation counts and S ratios remain null.

The fixed controls use field size 2^13 and prime subgroup order 2003, an 11-bit
subgroup. The prefix dimensions 3 and 6 yield 8 and 60 actual usable base points,
with 4 and 29 folded columns. These are toy exact-curve controls, not a security
boundary claim. Ordinary preparation/query failures are retained; the inputs
are not planted decompositions.

## Exact independent validation

The tests compare all 2,002 nonzero subgroup queries for both two-summand arms
on both bases: 8,008 queries. An independent Python point-pair oracle checks
relation presence, signed sums and matching bases. Full recovery controls cover
the frozen seeds, failure/single-use behavior, parallel independent workspaces,
corrupted final scalar replay and rebuilt UBSan components.

The offline auditor reconstructs S3 or S4 as appropriate, checks the complete
Boolean basis from original equations, checks all returned signed witnesses and
the first-usable root prefix, independently reconstructs modular matrix rank,
replays column logs and final scalars, and reconstructs the union-excluded
fixture. It validates canonical candidate/workload/run identities, stage
accounting, source/build/binary receipts and the recoverable journal. It rejects
altered roots, basis terms, native identities, pairing and omitted online work.
Audit caches only repeated offline proofs; measured contexts do not reuse them.

`PDP2eval` and `PDP2cond` are registered in AGENTS.md. The manifest records the
actual summand count, S3/S4 construction, solver, certificate, bounds and full
source identity. The candidate identifier changes when that implementation
changes. Merely substituting a two-summand workspace under a PDP3 label would
be invalid.

## Reproduction

These jobs use ordinary Python and C++; they do not invoke Sage.

```sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python experiments/groebner-perf-20260924/round27/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round28 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round28/conditional_measure.py --correctness-only --repetitions 2 --output /tmp/conditional-ic-correctness.json.gz
python experiments/groebner-perf-20260924/round28/conditional_audit.py /tmp/conditional-ic-correctness.json.gz
python experiments/groebner-perf-20260924/round28/conditional_measure.py --repetitions 31 --output /tmp/conditional-ic-paired.json.gz
python experiments/groebner-perf-20260924/round28/conditional_audit.py /tmp/conditional-ic-paired.json.gz
```

Use fresh output paths; existing reports and journals cannot be overwritten.
Timing qualification requires the declared load gate at entry, every group
boundary and exit. Correctness-only reports never qualify for speedup claims.
Every frozen point retains its own paired confidence interval and same-point
rho/IC ratio. The CI workflow rebuilds on Linux and macOS; a rejected timing
admission remains an explicit zero-trial result.

This integration does not establish a general F4/F5 improvement, a new F6
algorithm, a high-regularity asymptotic result or a GPU crossover. Those remain
separate experiments with their own complete-operation acceptance gates.

## Admitted physical M4 Pro comparison

The 31-pair run verifies 576 complete IC recoveries and 192 same-point rho
controls, including 18 IC and six rho warmups. Every initial/group/final load
check passes on the 14-logical-CPU physical M4 Pro (entry 7.545, exit 8.037).
The host runs macOS 26.6 ARM64, Python 3.13.1 and NumPy 2.4.0.
Load admission is necessary and does not establish exclusive host access.

The field has 2^13 elements; the subgroup has order 2003. Each cell below is
one frozen previously unseen public point. Preparation remains separate.
Times are medians in milliseconds; ratios are paired geometric means with
individual, unadjusted 95% bootstrap intervals.

| Actual base points | Public point (x,y) | Three-eval ms | Two-eval ms | Two-conditional ms | Same-point rho ms | rho / two-conditional [95%] | two-eval / two-conditional [95%] |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 8 | (5948,4412) | 4.583708 | 8.311083 | 2.932458 | 0.460000 | 0.178 [0.162, 0.199] | 2.886 [2.756, 3.026] |
| 8 | (5292,2374) | 11.247875 | 9.735917 | 3.443042 | 0.590000 | 0.174 [0.165, 0.182] | 2.796 [2.678, 2.897] |
| 8 | (4029,4301) | 12.184916 | 10.590209 | 3.683541 | 0.447792 | 0.121 [0.117, 0.125] | 2.861 [2.791, 2.923] |
| 60 | (5948,4412) | 1.629667 | 0.634583 | 0.471667 | 0.458625 | 1.012 [0.965, 1.074] | 1.348 [1.295, 1.407] |
| 60 | (5292,2374) | 1.708333 | 0.789666 | 0.546416 | 0.553625 | 1.071 [1.004, 1.149] | 1.435 [1.380, 1.490] |
| 60 | (4029,4301) | 1.898208 | 0.784958 | 0.543167 | 0.427917 | 0.822 [0.783, 0.869] | 1.461 [1.406, 1.518] |

Conditional solving improves all six complete recoveries over the matched
two-summand evaluation arm, by 2.80–2.89× on the smaller base and 1.35–1.46×
on the larger base. Comparing the complete two-summand conditional pipeline
with the prior three-summand pipeline gives 1.56–3.55×, but that comparison
changes the decomposition strategy and includes its changed attempt count.

The rho comparison is mixed: four points remain slower, one interval contains
one, and one has a narrow individual interval above one. This run does not
establish a repeatable general IC advantage. A confirmation and hosted runs
are needed to assess that narrow result. The pointwise ratios must not be
replaced with an average across targets or multiplied by prior component gains.

The ordinary preparation stream reaches full rank in 106 versus 356 attempts
on the smaller base, and seven versus 275 on the larger base, for three-summand
versus two-summand collection respectively. Every failed ordinary attempt is
retained. Median preparation is roughly 32 versus 38 ms on the smaller base
and 75 versus 89 ms on the larger base for three-eval versus two-conditional;
these costs are separate from the declared online interval.

The exact candidate IDs, workload IDs, online phases, target attempt status
mixes, separate preparation costs and all paired intervals are retained in
`results/paired-audit.json`. `results/paired-evidence.json` binds the complete
raw report and hash-chained journal retained in the task evidence archive.
The committed correctness trace has full source/build snapshots and raw
mathematical evidence; CI reconstructs and audits it against the same sources.

## Final-source physical confirmation

A second admitted 31-pair run verifies another 576 complete IC recoveries and
192 same-point rho controls, including 24 total warmups. The only source change
is removal of a trailing blank line in the offline auditor; its Python AST is
identical. The earlier implementation/evidence remains at commit `5779c56`.
The committed current-source correctness trace is under `results/final/`; CI
re-audits that trace. Every numerical source in the final report is unchanged
by the later documentation and artifact commit.

| Actual base points | Public point (x,y) | Three-eval ms | Two-eval ms | Two-conditional ms | Same-point rho ms | rho / two-conditional [95%] | two-eval / two-conditional [95%] |
| ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| 8 | (5948,4412) | 4.456042 | 8.175792 | 2.963708 | 0.462458 | 0.170 [0.155, 0.190] | 2.775 [2.722, 2.826] |
| 8 | (5292,2374) | 10.831667 | 9.466041 | 3.403666 | 0.580000 | 0.172 [0.162, 0.182] | 2.798 [2.649, 2.999] |
| 8 | (4029,4301) | 11.887000 | 10.344417 | 3.713375 | 0.444208 | 0.120 [0.116, 0.124] | 2.771 [2.714, 2.822] |
| 60 | (5948,4412) | 1.602667 | 0.622917 | 0.456458 | 0.447625 | 1.016 [0.970, 1.075] | 1.377 [1.332, 1.421] |
| 60 | (5292,2374) | 1.686209 | 0.769500 | 0.549333 | 0.551417 | 1.063 [1.006, 1.128] | 1.410 [1.364, 1.461] |
| 60 | (4029,4301) | 1.883667 | 0.793708 | 0.537000 | 0.435125 | 0.832 [0.795, 0.882] | 1.503 [1.432, 1.602] |

The full recovery gain over two-eval repeats at 2.77–2.80× on the smaller base
and 1.38–1.50× on the larger one. Changing the full pipeline from three-eval to
two-conditional gives 1.50–3.54×. The point (5292,2374) on the larger base again
has a narrow individual rho/IC interval above one, with geometric ratio 1.063;
its median ratio is close to parity. The other larger-base points are near
parity or slower. This is a repeated result for that exact toy point on this
physical host, not a broad IC advantage. Hosted confirmation and held-out
workloads remain distinct questions. Individual intervals are unadjusted for
multiple comparisons. Source identities, exact candidate IDs, full phases and
all ratios remain in `results/final/confirmation-audit.json`.
