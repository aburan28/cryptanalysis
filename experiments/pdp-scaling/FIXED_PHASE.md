# Fixed-phase PDP reuse: experiment and tracking plan

This is a **PDP stage diagnostic**, not a complete index-calculus attack or a
rho crossover. Work lives in `aburan28/cryptanalysis`, alongside the existing
`experiments/pdp-scaling` harness. `aburan28/crypto` is the upstream research
reference; this experiment does not modify either repo's production solvers.

## Hypothesis and predeclared gate

Fix three Frobenius phases outside the algebra, parameterize each summand by
linear payload bits, and amortize symbolic construction and solver knowledge
across blind targets. Does a chained S3 circuit, with or without external
payload guessing, lower the total PDP cost relative to the existing direct
S4 descent model?

Before the matched measurement, the engineering gate is: at least 20% lower
**total PDP CPU cost** than the cold numeric-target ANF baseline, on both seed
sets at a given (n,l,phase pattern), with every target decided correctly and no
missing completions. A configuration with timeouts cannot pass. This is a
local diagnostic threshold, not a statistical confidence claim. New seeds
and larger fields are required before any scaling inference.

The numerical baseline is the existing `descend.py` S4 model with its basis
map generalized to fixed phases. Tests compare the zero-phase ANF exactly
against `descend.descend`; the new baseline shares point verification with
the other contenders, not the symbolic encoding. A small-field point MITM
oracle independently establishes every verdict before solving, but supplies
no solutions, factor-base tables, signs or partial sums to the solver.

For a signed factor base of size B in a prime subgroup of order r, the
heuristic generic density of unordered m-term sums is about B^m/(m! r), capped
at one (collisions, phase restrictions and special relations alter it).
This counting heuristic is **not a lower bound on arbitrary algebraic
algorithms**. No claimed improvement to an attack exponent follows from it.
The ultimate reference remains Frobenius/negation rho on the same group,
including setup, relation collection, linear algebra and scalar recovery.
Those complete-pipeline measurements are outstanding, so there is no numeric
ratio to rho in this report.

## Implemented variants

All variants use E0: y²+xy=x³+1, b=1, in the existing polynomial-basis field.
V is span(1,z,...,z^(l-1)); block i uses sigma^(phase_i)(V). This is a control
family, **not** the separate auxiliary-field 26-bit cubic construction.

- `anf-s4/cold`: specialize and fully expand S4 at each numeric target,
  encode its Boolean ANF as AND gates and native XOR equations, fresh solver.
- `s4`: the symmetrized twelve-term S4 **circuit**. Its intermediate field
  coordinate is eliminated, but Boolean gate variables remain. It is not an
  expanded high-degree ANF measurement and not a Gröbner computation.
- `s3-chain`: two S3 circuits plus an explicit branch for P1+P2=infinity.
  A chain that omitted this branch could incorrectly reject valid PDPs.
- `cold`: rebuild circuit and solver for every target.
- `template`: construct the circuit once, load a fresh solver for each target.
- `incremental`: keep the circuit and solver; select each target with temporary
  assumptions. Learned clauses are reused by CryptoMiniSat under its normal
  assumption semantics. No target-dependent pivots or unconditional target
  unit clauses are reused.
- `guess_bits=2`: enumerate the first two payload bits outside the solver;
  the **one per-target** search budget covers all guesses and rejected models.

Phase tuples `(0,0,0)` and `(0,1,2)` are separate workloads. Compare methods
within the same tuple; do not report reduced cost on one tuple as an
improvement over another tuple with different coverage. No claim is made
that this scans the whole Frobenius-stable union.

## Correctness and accounting

Every SAT tuple is lifted to rational points, checked in the order-r subgroup,
and tested under all signs by actual addition against the exact target.
A spurious model is blocked with a **target-guarded** payload clause and search
continues. Unknown/timeouts remain unknown. The tests exhaust the small
order-29 subgroup, repeat it backwards with target signs reversed, exercise
the infinity branch, compare circuit multiplication against independent field
arithmetic, compare S4 against a resultant, and check the Boolean export.

Benchmark targets are sampled without replacement **up to sign**, in a prime
order-r subgroup. There are no planted decompositions and no repeated target
x-coordinates within a run. Seed 17 is development; seed 911 is the preselected
holdout. Configuration order is shuffled using a fixed, recorded seed.

The headline here is total **process CPU seconds for the PDP workload**,
including field setup, symbolic construction, solver loading, failed attempts,
hybrid guesses, lifting, subgroup checks, sign search and result handling.
Solver and verification timers are subsets, not additional charges. Corpus
creation and the independent exhaustive oracle are excluded instrumentation,
with their CPU cost reported explicitly. This is not an operation-normalized
attack-speed claim. No GPU, F4, memory scaling or degree-131 performance is
inferred from these timings. Per-target timeout covers search including
verification and blocking, not circuit setup. Results retain every timeout.

`cpu_s_per_verified` counts verified decompositions, **not independent
relations or rank growth**. Subgroup log-column folding and linear algebra
are not implemented in this stage experiment. All matched total-cost ratios
require equal completions and verdicts. Cold campaign cost is charged first;
warm reuse always names the target count (eight or the explicit CLI value).

## Reproduce

```sh
cd experiments/pdp-scaling
python3 -m pip install pycryptosat==5.16.0
python3 -m unittest -v test_fixed_phase.py
python3 fixed_phase.py --n 7 --l 4 --targets 8 --seeds 17 911 \
  --timeout 2 --out results/fixed_phase_matched.json
python3 fixed_phase.py --n 13 --l 6 --targets 4 --seeds 17 911 \
  --timeout 1 --out results/fixed_phase_larger.json
```

Output paths must be new. JSON includes source hashes, base commit, versions,
configuration order, corpus digest, exact targets, witnesses, statuses,
phase CPU times and circuit sizes. Preliminary smoke timings are excluded;
only the frozen matched runs below are used for the gate.

## Measured outcome

The full variant table is [results/fixed_phase_summary.md](results/fixed_phase_summary.md).
These are engineering-stage diagnostics; no row establishes an algorithmic
advance or a rho crossover.

At n=7, l=4, every method decided all 16 targets across the two preselected
seeds. Chained S3 with incremental state and two guessed bits cost 1.1901 s
against the numeric ANF baseline's 4.7747 s for phases (0,0,0), and 1.5740 s
against 4.6579 s for phases (0,1,2). Candidate/baseline CPU ratios are 0.249
and 0.338. Both pass the predeclared per-seed stage gate. The fresh S3 chain
already costs less than half the baseline, so the whole gain must not be
attributed to cache reuse. Guessing two bits improves the reused chain only
modestly in this sample; it is not evidence of a better exponent.

Only two and four decompositions, respectively, were found across those 16
targets; the remaining correctly decided targets are negative PDPs. These
are verified sums, not a measured full-rank relation collection. The direct
S4 circuit fails the gate even with reuse: it costs more than the ANF baseline.

The n=13, l=6 probe uses four blind targets per seed and a one-second search
budget. All 144 attempts timed out; none establishes a decided verdict or
a cost ratio at that size. The unresolved instances remain visible in the table. It tests
where this prototype stops completing, not how quickly a full-size attack
will run. Repeated budgets, optimized compiled backends, larger corpora and
F4 comparisons are follow-up work; no extrapolation is fitted here.

Regenerate the table with:

```sh
python3 fixed_phase_summary.py results/fixed_phase_matched.json \
  results/fixed_phase_larger.json --out /tmp/fixed_phase_summary.md
```

## Gröbner replay

`Template.boolean_equations()` produces the exact specialized Boolean
system, including target/guess assignments and both chain branches.
`export_msolve()` adds field equations and writes the existing harness's
msolve input format. Example:

```python
from fixed_phase import Template
from gf2n import GF2n
model = Template(GF2n(7), 4, (0, 1, 2), 's3-chain')
model.export_msolve('/tmp/fixed_phase.ms', target_x=12, guess_bits=2, guess=0)
```

Run the exported gate-variable system through the existing msolve/F4 backend
and record matrix rows/columns, degree reached, memory and all slices. The
export has been checked against SAT assignments, but **no F4 run or Gröbner
speed improvement is claimed** here. Caching a symbolic circuit does not
establish that a specialized Gröbner basis or pivot sequence is reusable.

## Tracking checklist

- [x] Inspect existing decomposition, polynomial-reuse and hybrid work in both repos.
- [x] Implement matched fixed-phase controls and an independent numeric ANF baseline.
- [x] Implement cold/template/incremental and bounded external guesses.
- [x] Handle chain infinity cases and verify actual subgroup point relations.
- [x] Add exact Boolean-system export for Gröbner replay.
- [x] Record matched pilot and larger-field results and apply the gate.
- [ ] Run F4 on the same targets; record peak matrices, solving degree and memory.
- [ ] Test the 26-bit auxiliary-field payload family and alternative sparse bases.
- [ ] Extend to four/five/six summands, including all intermediate-infinity cases.
- [ ] Include phase-pattern selection cost and union coverage in relation yield.
- [ ] Evaluate bounded residual matching with construction and merging charged.
- [ ] Run complete matched DLP recovery versus folded rho with operation counters,
      independent holdouts, all setup and linear algebra included.

The follow-up stopping rule is to abandon a variant as a performance candidate
if it loses to the baseline at matched completions on both seed sets; retain
it as a correctness/control backend. Improvements to setup alone remain
engineering diagnostics. An exponent or rho claim requires the final unchecked
item, not extrapolation from these toy fields.

## Explicit toy-domain follow-up

[TOY_DOMAIN.md](TOY_DOMAIN.md) records a bounded, fully charged admissibility
filter and fresh paired measurements against the original incremental chain.
The earlier results above are retained; the filter is an exponential toy
control, not a replacement for the unresolved scalable membership problem.
