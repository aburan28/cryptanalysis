# The index-calculus benchmarking framework

A harness for asking **"what does changing *this* stage do to everything
downstream?"** about elliptic-curve index calculus, and for getting an
answer that is a measurement rather than an argument.

An index-calculus attack is five stages. Most published comparisons
change one of them and report the total, which leaves the reader unable
to tell whether a gain came from the thing being claimed or from
something else that moved with it. This framework makes each stage a
plug point, runs the whole pipeline end to end against a planted
logarithm, and reports **every stage's cost in one unit** — so a change
is visible where it lands, not only in the total.

```
  instance ──► factor base ──► targets ──► decomposition ──► relations ──► logarithm
                   │              │             │                │             │
           FactorBaseBuilder   Targets   DecompositionOracle  RelationSolver  verified
                                              │
                                        SystemSolver          ← F4, F5, XL, SAT, …
```

---

## 1. Quick start

```bash
cargo build --release --bin ca-ic

# What can be plugged in where, and what parameters each plug-in reads.
ic bench --list

# One configuration, end to end, on an 18-bit prime-order curve.
ic bench --bits 18 \
    --factor-base prime-abscissa:size=32 \
    --oracle mitm:negation_folded=1 \
    --targets walk \
    --repeats 3

# An algebraic oracle: Weil-descend the summation polynomial over the
# base's subspace and choose the engine that solves it.  The solver's
# work is priced into S, so this row and the pair-table row above it
# are comparable end to end.
ic bench --char2-degree 13 \
    --factor-base binary-subspace:dimension=6 \
    --oracle descent-algebraic:m=2 \
    --solver f4-f2

# The engines on their own, paired: every engine solves the same
# seeded descent systems, interleaved, checked against the exhaustive
# reference.  A stage diagnostic, not a speed (§7).
ic descent --cells 17:9:2 --targets 8 --repeats 3 \
    --solver buchberger-f2 --solver f4-f2 --solver matrix-f5 \
    --solver crossbred-f2 --solver fes-f2

# The relation matrix is a stage too.
ic bench --bits 20 \
    --factor-base prime-abscissa:size=256 \
    --oracle mitm:negation_folded=1 \
    --linalg structured-gauss

# A sweep: every combination in the matrix, one table.
ic bench --sweep docs/ic/sweeps/factor-base-size.json \
    --out docs/ic/runs/my-sweep-2026-09-22.json
```

The table that comes out:

```
| instance    | configuration                  | base | cols | pts/col | hit rate | trials | rows | rank |   S   | correct |
| bench-18bit | prime-abscissa[size=8]  + mitm |   16 |    8 |     2.0 |    0.001 |   2219 |    3 |    3 |  6.68 | yes     |
| bench-18bit | prime-abscissa[size=32] + mitm |   64 |   32 |     2.0 |    0.008 |   1273 |   10 |   10 |  6.62 | yes     |
| bench-18bit | prime-abscissa[size=128]+ mitm |  256 |  128 |     2.0 |    0.110 |    757 |   83 |   83 | 36.14 | yes     |
```

Read across a row and the trade-off is explicit: a bigger base raises
the hit rate (`0.001 → 0.110`), which cuts the targets needed
(`2219 → 757`), which raises the matrix rows (`3 → 83`). `S` is the sum
of all of it, and it is not monotone — that is the point.

---

## 2. The unit, and why everything is in it

Every cost in a report is in **group-addition equivalents**: one
addition on the curve is `1`. Native work that is not a group operation
— square roots, table lookups, SAT conflicts, monomial operations,
matrix multiply-subtracts — is counted in its own unit and converted
once, at the end, by ratios pinned in
[`docs/ic/calibration.json`](calibration.json).

The headline is

```
S = total group-addition equivalents / sqrt(r)
```

where `r` is the prime subgroup order. Dividing by `√r` makes Pollard
rho a constant (`S ≈ 1.3`) at every size, so `S` is comparable across
instances and "is this better than rho" is reading one column.

Three rules follow, and the framework enforces what it can:

- **Every phase is inside `S`.** Factor-base construction, table setup,
  failed decompositions, linear algebra and verification. A number that
  prices one phase is a *stage diagnostic*, never a speed.
- **Operation counts are the metric.** Wall time is carried as a
  practicality note. Counts survive a change of hardware; seconds do
  not.
- **A row without a verified answer is not a result.** The runner checks
  the recovered logarithm against the planted one. A configuration that
  fails is reported with `correct: NO` or `gave up`, not dropped.

---

## 3. Reading a report

`ic bench` emits JSON (with `--out`) and a Markdown table. The JSON
carries strictly more: every stage's `PhaseCost` with its native
counters, so you can re-derive any column.

### Instance

| field | meaning |
|:--|:--|
| `instance`, `regime` | the curve and its family |
| `r`, `log2_r` | the subgroup order the logarithm lives in |
| `group_order` | `#E` |

### Factor base

| field | meaning |
|:--|:--|
| `signed_points` | entries in the base; both `P` and `−P` are entries |
| `abscissae` | distinct `x`-coordinates |
| `columns` | **unknowns in the relation matrix** |
| `points_per_column` | signed points per unknown: the fold, measured |
| `cost` | what building it cost, inside `S` |

`points_per_column` is the one to watch. A base that folds `P` and `−P`
onto one column reads `2.0`; a Koblitz base that folds a whole signed
Frobenius orbit reads `2n`. The fold is what cuts the relations needed,
so this column is the cause of the `rows` column further along.

### Decomposition

| field | meaning |
|:--|:--|
| `summands` | factor-base points in a relation |
| `targets_tried` | points the oracle was asked about |
| `relations_found` | how many decomposed |
| `hit_rate` | `relations_found / targets_tried` |
| `setup` | what `prepare` cost: the pair table, or nothing for an oracle that builds none — its own phase, inside `S`, so the same base reads the same beside every oracle |
| `cost` | the whole stage, including the failures |
| `system` | the algebraic system's shape, when the oracle built one |
| `solver` | what the polynomial solver cost, when one was used |

The failures are the expensive part and they are inside `cost`. An
oracle priced only on its successes is priced wrong.

Two native counters in `cost` belong to algebraic oracles only.
`lift_failures` counts solver solutions that lifted to no relation;
`unliftable_systems` counts systems the solver decided satisfiable none
of whose solutions lifted. Neither is a defect: a summation polynomial
vanishes over the algebraic closure, so a solution may name abscissae
whose points lie on the quadratic twist, which the pair table never
sees. They are counted apart from "did not decompose" so the hit rate
can be read against what the solver actually found.

### Solver (algebraic oracles only)

| field | meaning |
|:--|:--|
| `name`, `calls` | the engine, and how many systems it was handed |
| `ops`, `op_unit` | the engine's own count, and what it counts |
| `gae`, `priced_by` | that count in the unit, and how it got there (below) |
| `solving_degree_mean`, `solving_degree_max` | highest degree at which a run learned something, averaged and at worst |
| `semi_regular_degree` | the degree a system with **no exploitable structure** would reach |
| `degree_over_bound` | their ratio — below one is the structure the solver found |
| `budget_exceeded` | calls that ran out of budget, counted apart from refutations |
| `wall_ns`, `peak_bytes` | the practicality note: time, and the largest basis or matrix held |
| `extra` | the engine's own counters (S-polynomials, pairs pruned, conflicts, …) |

The degree bound is derived, not fitted: it is the index of the first
non-positive coefficient of `(1+t)^v / Π_i (1 + t^{d_i})`
(Bardet–Faugère–Salvy) for `v` boolean variables and equation degrees
`d_i`. See §14.3 of
[`RESEARCH_IC_BOUNDARY_LEDGER.md`](https://github.com/aburan28/crypto/blob/main/research/notes/index-calculus/RESEARCH_IC_BOUNDARY_LEDGER.md).

`budget_exceeded` is separate from "did not decompose" on purpose. An
oracle that reports a timeout as no-solution silently lowers its own hit
rate, and every downstream number inherits the error.

**How the solver reaches `S`.** The engine's `ops` are converted to
group-addition equivalents and added to the decomposition phase, so
`S` carries them; `priced_by` says how the conversion was done:

| `priced_by` | meaning |
|:--|:--|
| `pinned` | the unit is `word XORs` — the dense Macaulay row operation §5 of the ledger note priced matrix-F4 in — and the calibration's `ns_per_word_xor` was **replaced by the table's ratio** for this instance (`Calibration::pin` records which units it pinned in `pinned_units`; the report's `calibration_pins` lists them): comparable across hosts and runs |
| `measured` | priced from this host's own measurement: for `word XORs` on an instance the table does not carry, the count times the measured `ns_per_word_xor` ratio; for every other unit (Buchberger monomial operations, SAT conflicts, exhaustive monomial tests), the engine's wall time over the measured addition time. Honest, but host-dependent, and §12 of the ledger note is why a ratio between two `measured` rows from different hosts means nothing. `ns_per_op` records the factor the price rests on in both cases |
| `unpriced` | no calibration at all (a library call with `Calibration::default()`); the solver's work is in `ops` and **not** in `S`, and the row says so rather than quietly dropping it |

Only `word XORs` is priced by count on purpose. The first frozen
solver sweep measured a Buchberger "monomial operation" at about 50 ns
on the calibration host against 0.4 ns for a word XOR; pricing the one
at the other's ratio would have flattered the engine a hundredfold,
which is §6's "changing the unit" in one line of code. An engine whose
unit deserves a pinned ratio gets one the way §12 of the ledger note
pinned the others — measured, recorded in `calibration.json`, named —
not by being added to a list.

A comparison between engines is only as good as the weakest `priced_by`
in it. Two `pinned` rows compare operation counts; a `pinned` row
against a `measured` row compares an operation count against a
stopwatch, and the table should say which is which.

### Linear algebra, verification, total

| field | meaning |
|:--|:--|
| `name` | the matrix: `incremental-gauss` or `structured-gauss` |
| `rows`, `rank`, `dependent` | relations added, rank reached, and the ones that added nothing |
| `work`, `work_unit` | the method's own count (`row_ops` for an elimination) |
| `recovered`, `verified` | the logarithm found, and whether it is the planted one |
| `total_gae`, `s` | the whole pipeline, and it over `√r` |
| `s_over_rho` | against the matched counted Pollard rho on the same instance, when supplied |

### The rho reference

`ic bench` runs the reference before any configuration, on the same
subgroup and the same planted logarithms (`--rho-runs`, default 16),
and every row's `s_over_rho` divides by its mean `S`.  It is the
**matched** walk the accounting contract asks for: it uses the
automorphisms the curve actually has, because a generic algorithm may
use them too.

| curve | `rho_reference` (prices the column) | also in the report |
|:--|:--|:--|
| generic prime, random binary | the negation-map walk, `A = 2` (`ic_boundary::rho_reference_negation`) | `rho_reference_plain`: the plain walk on points, `A = 1`, on the same seeds |
| Koblitz | the cheaper, by mean `S`, of the signed-Frobenius walk (`A = 2n`) and the negation walk | the other in `rho_reference_candidates`; the plain walk |

The negation walk is tuned so that its `S` is rho's and not its set-up's.
Walk starts cost one addition each, and distinguished points come about
every `r^{1/4}` steps. The jump table is sized to the subgroup
(`rho_jumps_for`, calibrated in ledger §18.3). Fruitless cycles are
handled by the Wiener–Zuccherato look-ahead and a deterministic doubling
escape. Every operation it performs is charged, and its `counters` say
where each one went.

Through ledger §17 the column divided by the plain walk. That walk's
`S` is mostly set-up at toy sizes: `14.8` at `r ≈ 2^{12}`, where the
negation walk measures `2.6`. So a frozen report's `vs rho` from before
§18 is generous to index calculus. `ic rho --reprice FILE` re-prices
one against the matched walk. It first replays the frozen walk on the
recorded seeds and refuses to re-price if any run differs.

**A figure that solves `k` targets at once needs rho at the same `k`.**
`ic bench` and `ic boundary` solve one target, so the single-target walk
is their reference.  A pipeline that amortises one build over `k`
targets and quotes its total over `k·√r` must divide by batch rho
(Kuhn–Struik): `k` targets in sequence, jumps in `G` only, and one table
of distinguished points, so a later target can finish on an earlier
one's trail (`ic_boundary::rho_batch_with`).  At `k = 32` that costs
about a fifth of one target alone (ledger §19).

    ./target/release/ca-ic rho --batch-koblitz 0/41,0/53 --batch-sizes 1,4,16,32 --batches 16

The walk is generic over the classes it moves between
(`ic_boundary::RhoClasses`): points, `{P, −P}`, and on a Koblitz curve
the signed Frobenius classes (`SignedFrobeniusClasses`).  Those are
canonicalised by the least normal-basis rotation, and `x` and `y` are
carried there by table.  The count charges group operations only.  What
a step's canonicalisation costs on top, in a batched unit, is measured
by `examples/koblitz_reference_prices.rs`.

---

## 4. The stage contracts

Each stage is a Rust trait in
[`src/cryptanalysis/ic_framework/stages.rs`](../../src/cryptanalysis/ic_framework/stages.rs).
What follows is the contract in prose; the doc comments on the traits
are the normative version.

### Every stage: charge what you spend

Each stage receives `&mut GroupOps` and **must charge every group
operation to it**. This is not bookkeeping hygiene — the end-to-end
total is the sum of the stages, so a stage doing uncounted work makes
the total a fiction, and the fiction is always in the flattering
direction.

Native work that is not a group operation goes into the stage's own
counters (`PhaseCost::count("lookups", n)`) and is converted once by the
calibration. If your plug-in invents a new kind of work, count it under
a new name and say what the name means; an unconverted counter is
visible in the JSON and will not silently vanish into the total.

### `FactorBaseBuilder` — which points, and which unknowns

Returns a `FactorBase` with its **column map**: which unknown each
signed point contributes to, and with what coefficient. The column map
is the builder's job because it is where the symmetry lives — negation
folding, Frobenius-orbit folding — and those change the number of
relations the pipeline needs.

**Must**: charge the construction to `ops`. **Must not**: return a base
whose column map does not respect the group law, since the relation
matrix will then be solving a different problem than the one that was
posed. (The runner's verification catches this, loudly.)

### `Targets` — where trial points come from

A small enum rather than a trait, because there are two designs that
matter and the difference between them is a documented result rather
than an extension point:

- `random` — a fresh `[a]G + [b]Q` per trial: two scalar
  multiplications, about `3·log₂r` additions.
- `walk` — an r-adding walk: one addition per trial, with a guard that
  no target is presented twice.

The guard matters. Without it a run can terminate because it decomposed
the same point twice, which is a *collision* and not a relation — a
generic result dressed as an index-calculus one. See §10.2 of the
ledger note for the round where that was caught.

### `DecompositionOracle` — the point decomposition problem

Given `R`, return indices of `m` factor-base points summing to it, or
`None`. `None` is the common case and must be cheap.

**Must**: charge group operations to `ops` and native work to
`counters`. **Must not**: return a decomposition that does not actually
sum to `R` — the relation matrix will accept it and the pipeline will
recover a wrong logarithm, which the verification will then report as a
failure rather than a result.

`prepare` is called once per run, after the base exists, for tables and
precomputation. That cost is part of `S`.

An oracle that solves an algebraic system reports the system through
`last_system` and its running totals through `solver_totals`, so the
degree columns are filled from the real systems rather than from a model
of them, and the runner prices the totals into `S`. The shipped one is
`descent-algebraic`: it Weil-descends `S_{m+1}` over the base's
abscissa subspace, hands the boolean system to whichever `SystemSolver`
was named, and lifts each solution to signed base points summing to the
target. It needs a base that exposes a subspace (`binary-subspace`,
`koblitz-orbit`). The descent is symbolic — the summation polynomial
expanded term by term in `F_{2^n}[v]/(v² − v)`, where squaring is
linear and a product of monomials is their union — so it builds no
table and is capped only by the monomial mask: `m·n' ≤ 64`, i.e.
`n' ≤ 32` at `m = 2` and `n' ≤ 21` at `m = 3`. `S3` descends to
quadratics, `S4` to degree at most six. Above that it is the engine
that limits a row, and it says so through `accepts`.

### `SystemSolver` — F4, F5, XL, SAT, anything

**This is the plug point most people want.** It takes a boolean
polynomial system and returns its solutions with a cost record. It
knows nothing about elliptic curves and an implementer does not need
to.

```rust
pub trait SystemSolver: Send + Sync {
    fn name(&self) -> &str;
    fn describe(&self) -> String;
    fn parameters(&self) -> &[(&str, &str)] { &[] }
    fn accepts(&self, shape: &SystemShape) -> bool { true }
    fn finds_every_solution(&self) -> bool { true }
    fn solve(&self, system: &BooleanSystem, params: &Params, budget: Option<Duration>)
        -> (SolverVerdict, SolverCost);
}
```

What ships behind it (`ic bench --list` prints each one's parameters):

| name | engine | native unit | limits |
|:--|:--|:--|:--|
| `f4-f2` | Faugère's F4 over `F_2[v]/(v² − v)`: normal strategy, Gebauer–Möller criteria, the field products `v·g` as pairs, symbolic preprocessing, bit-packed elimination; a full reduced basis, solutions read off its linear elements ([`pq_f4_f2.rs`](../../src/cryptanalysis/pq_f4_f2.rs)) | word XORs (elimination only) | matrix size; the budget |
| `matrix-f4` | the Koblitz oracle's hybrid: Macaulay matrices to a fixed degree (`max_degree`, default 3), propagation, splitting (`split`) | word XORs (elimination only) | `node_budget` |
| `matrix-f5` | the same, leaving out the rows the Boolean F5 criterion predicts to reduce to zero | word XORs (elimination only) | `node_budget` |
| `inherited-f4` | the same, children specialising their parent's reduced basis | word XORs (elimination, specialisation and linear elimination only) | `node_budget` |
| `crossbred-f2` | Joux–Vitse: a Macaulay left kernel at degree `D`, then `2^k` bit-sliced linear solves | word operations (partial) | parameters that do not fit the system are a budget verdict |
| `buchberger-f2` | Buchberger over the boolean ring, one pair at a time, coprime and chain criteria, closed under the field equations since 34154ed9 — the frozen rows of ledger §14–§17 were measured on the earlier pair-only engine, whose degree is an upper bound (§17.1, §17.7) | monomial operations | the budget; enumerates for solutions up to 26 unknowns |
| `xl-f2` | XL: multiply out to degree `n_vars`, linearise | monomial operations (modelled) | declines above 10 unknowns |
| `sat-cdcl` | CDCL with Tseitin monomials and native parity rows; **one model per call** | conflicts | `sat_conflict_budget` |
| `fes-f2` | fast exhaustive search, libfes-lite's Gray code: two word XORs per point | word XORs (Gray-code steps) | quadratic systems, ≤ 32 unknowns, ≤ 64 equations |
| `fes-f2-wide` | the same over 16 (AVX-512) or 8 (AVX2) sub-cubes per Gray-code step, the last four or three unknowns fixed per 32-bit lane; the first 32 equations in the lanes, the rest filtering the candidates; the scalar walk where the lanes do not fit ([`mq_fes.rs`](../../src/cryptanalysis/mq_fes.rs)) | vector XORs (Gray-code steps, *k* lanes) | quadratic systems, ≤ 36 unknowns; 3–4× `fes-f2` here |
| `exhaustive` | every equation at every point, stopping at the first that fails | monomial tests (performed) | 26 unknowns |

The exhaustive searches are the **reference**, not a strawman:
`fes-f2-wide` (or `fes-f2` on a host without the vector instructions)
wherever the system is quadratic (every two-summand descent),
`exhaustive` where it is not. An engine that does not beat the
strongest of them on a cell has not earned that cell.

The contract is short and all of it matters:

- **Count something.** `SolverCost::ops` with an `op_unit` naming it.
  An engine reporting only wall time cannot be compared across hosts
  and will not be accepted as a speed.
- **Respect the budget.** Return `BudgetExceeded`, never an unbounded
  run.
- **Never guess `Unsatisfiable`.** Say it only when the system is
  decided.
- **Report a degree if you have one.** `solving_degree` is the highest
  degree at which the run learned something new, and it is the one
  comparable against a degree bound. `degree_reached` may be higher and
  is a property of your selection strategy, not of the system. Getting
  this backwards produced a wrong conclusion in this repository once;
  see §14.4 of the ledger note.
- **Decline what you cannot do.** `accepts` lets a solver opt out of a
  shape rather than time out on every target of a sweep. The
  `descent-algebraic` oracle asks it once, at `prepare`, on the shape
  every system on that base will have, so a declined engine skips the
  row with a reason instead of running the relation phase for nothing.
  `xl-f2` is the shipped example: the repository's XL runs one pass at
  degree `n_vars` with no budget hook — about 150 seconds a call on a
  12-unknown descent against Buchberger's 7 milliseconds on the same
  systems — so it declines above ten unknowns.
- **Say whether you find every solution.** `finds_every_solution`
  defaults to `true`. An engine that returns one model per call (a SAT
  solver) overrides it to `false`: the accounting contract keeps
  first-solution and complete-enumeration engines on separate
  leaderboards, and a paired comparison checks a first-solution engine
  for membership in the reference's solution set rather than equality.
- **Qualify a partial count.** The runner prices a count by the
  calibrated word-XOR ratio only when `op_unit` is exactly
  `word XORs`, which asserts that the count covers the whole run. An
  engine that counts its elimination but not its matrix build (every
  F4-family engine here) says so in the unit — `word XORs (elimination
  only)` — and is priced by measured wall time instead. Leaving the
  qualifier off would price an incomplete count as a complete one,
  flattering the engine by whatever it left out.

### `RelationSolver` — the matrix

Accumulates relations and decides when the target's logarithm is
determined. Behind a trait because the choice between a dense
incremental elimination, structured Gaussian elimination and an
iterative method (Wiedemann, Lanczos) is a real lever and the one most
often left unpriced.

Two ship, chosen with `--linalg` (or the `linalg` key of a sweep):

| name | what it is | pivot | storage |
|:--|:--|:--|:--|
| `incremental-gauss` | dense reduced row echelon, maintained as rows arrive | leftmost non-zero | `rank × columns` |
| `structured-gauss` | sparse reduced row echelon, maintained as rows arrive | lightest column (Markowitz) | the non-zeros |

Both charge one `row_op` per non-zero multiply-subtract, so their
`work` columns compare directly; on the two- or three-non-zero rows an
index-calculus relation phase produces the pivot choice is worth a few
per cent of `row_ops` (538 against 582 on 63 rows over 121 columns),
and the real difference is the storage and the uncounted column scans,
which show in `wall_ns` first. The contract both obey: `add_row`
reduces the new row against the pivots held so far and answers
`Independent`, `Dependent` or `Inconsistent`; `pinned` says whether one
column is determined on its own. The loop calls them after every
relation, so an implementation must answer incrementally; a batch
method would re-solve on every call.

---

## 5. Adding a plug-in: a worked example

Suppose you have implemented F5 and want to know what it does to a
whole pipeline.

**Step 1 — implement the trait.** In your own module:

```rust
use crypto_lib::cryptanalysis::ic_framework::stages::*;
use std::collections::BTreeMap;
use std::time::{Duration, Instant};

pub struct F5;

impl SystemSolver for F5 {
    fn name(&self) -> &str { "f5" }

    fn describe(&self) -> String {
        "F5 with the signature criterion, over the boolean quotient".into()
    }

    fn parameters(&self) -> &[(&str, &str)] {
        &[("max_degree", "degree bound before giving up (default 12)")]
    }

    fn accepts(&self, shape: &SystemShape) -> bool {
        shape.n_vars <= 64
    }

    fn solve(&self, system: &BooleanSystem, params: &Params, budget: Option<Duration>)
        -> (SolverVerdict, SolverCost)
    {
        let started = Instant::now();
        let max_degree = params.u64_or("max_degree", 12).unwrap_or(12) as u32;

        // ... your engine here; suppose it yields:
        let (solutions, reductions, top_degree, useful_degree, timed_out) =
            my_f5(&system.equations, system.n_vars, max_degree, budget);

        let mut extra = BTreeMap::new();
        extra.insert("signature_rejections".into(), 0u64);

        let cost = SolverCost {
            ops: reductions,
            op_unit: "monomial operations".into(),
            wall_ns: started.elapsed().as_nanos() as u64,
            peak_bytes: 0,
            degree_reached: Some(top_degree),
            solving_degree: Some(useful_degree),
            timed_out,
            extra,
        };

        if timed_out                { return (SolverVerdict::BudgetExceeded, cost); }
        if solutions.is_empty()     { return (SolverVerdict::Unsatisfiable,  cost); }
        (SolverVerdict::Solved(solutions), cost)
    }
}
```

**Step 2 — register it.** Add it to `solver_registry()` in
[`solvers.rs`](../../src/cryptanalysis/ic_framework/solvers.rs):

```rust
pub fn solver_registry() -> Vec<Box<dyn SystemSolver>> {
    vec![
        Box::new(F4F2),
        Box::new(BuchbergerF2),
        // … the other shipped engines …
        Box::new(Exhaustive),
        Box::new(F5),            // ← yours
    ]
}
```

**Step 3 — check it agrees with the others.** The module's tests
already require every registered solver to find the same solution set
on random quadratic systems and on descent systems of both summand
counts, and to refute an unsatisfiable system. Your engine is now in
that loop; if it disagrees, the test names it.

```bash
cargo test --release --lib cryptanalysis::ic_framework
```

**Step 4 — measure it against the reference, on its own.** `ic descent
--solver f5 --solver fes-f2 --solver buchberger-f2 --repeats 3` runs
your engine on the frozen descent table's seeded targets beside the
reference and the baseline, interleaved per target, and checks every
answer against the reference's. `fes-f2` (quadratic systems) and
`exhaustive` (the rest) are not strawmen: they are the best algorithms
that already solve the same problem on the same instance. If your
engine cannot beat them on a cell, it has not earned that cell whatever
its asymptotics are said to be.

**Step 5 — measure the whole method.** The per-call ratio is a stage
diagnostic. What your engine does to `S` is the answer:

```bash
ic bench --sweep my-solver-sweep.json
```

**Step 6 — run the matched suite before claiming anything.**
[`research/ic_framework_engines_20260922/`](https://github.com/aburan28/crypto/blob/main/research/ic_framework_engines_20260922/README.md)
freezes the paired baseline/candidate comparison `AGENTS.md` §8 asks
every performance change to carry: `run.py --add-engine f5` reruns the
frozen engines with yours beside them, and `compare.py --manifest`
refuses the comparison if your run saw different inputs or decided them
differently.

The same four steps apply to a factor base (`FactorBaseBuilder`), an
oracle (`DecompositionOracle`) or a matrix (`RelationSolver`) — a
different trait, the same contract.

---

## 6. Sweeps

A sweep file names one instance and either an explicit list of
configurations or a **matrix** whose product is taken.

```json
{
  "instance": { "regime": "prime", "degree": 18 },
  "repeats": 2,
  "seed": 20260922,
  "max_trials": 2000000,
  "matrix": {
    "factor_base": ["prime-abscissa:size=16", "prime-abscissa:size=64"],
    "oracle":      ["subtract", "mitm", "mitm:negation_folded=1"],
    "targets":     ["random", "walk"]
  }
}
```

- `regime` is `prime`, `char2` or `koblitz`; `degree` is subgroup bits
  for `prime` and the field degree otherwise. A `char2` instance may
  set `max_cofactor` (default 8, as on the boundary ladders): a random
  curve whose cofactor is allowed to be large can hand back a tiny
  subgroup, and `S = ops / √r` over a tiny `r` means nothing against
  rho.
- A plug-in is `name` or `name:key=value,key=value`.
- The keys are the stages: `factor_base`, `oracle`, `targets`,
  `solver` (for `descent-algebraic`) and `linalg`. A key left out takes
  the command line's value.
- `configurations` takes an explicit list instead of, or as well as, a
  matrix — the way to put a reference row (the pair-table oracle on the
  same base) beside a matrix of candidates.
- A combination that does not apply to the regime is **skipped and
  reported**, not fatal: a matrix will contain combinations that do not
  exist, and the useful output is the ones that do plus a note on the
  rest.

Sweeps that ship, under [`docs/ic/sweeps/`](sweeps):

| file | the question it asks |
|:--|:--|
| `factor-base-size.json` | what the base size does to the hit rate, the trials, the matrix and `S` |
| `solver-engines.json` | what the polynomial-system engine does to the whole pipeline: the pair table as the reference row, then `descent-algebraic` once per engine, on one base |
| `solver-engines-n17.json` | the same question past the old truth-table cap: an 18-unknown descent on a degree-17 curve, which engines still finish, and at what cost |
| `relation-matrix.json` | what the matrix does: same relations, two eliminations, two base sizes |

---

## 7. Reporting what comes out

The repository's reporting rules are in [`AGENTS.md`](https://github.com/aburan28/crypto/blob/main/AGENTS.md)
and they apply to framework results. The short version:

- **State a boundary before measuring.** A floor (a counting or
  generic-group bound) and a reference (the best algorithm that already
  solves the problem). A thread that cannot state its boundary has not
  started.
- **One table, one unit, a ratio column.** Every variant is a row,
  including the reference and the unmodified baseline.
- **Classify the change**: *advance* (the ratio to the floor fell),
  *engineering* (`S` fell, ratio flat), *relabelling* (a headline count
  fell but `S` rose), *accounting* (the numbers changed, the algorithm
  did not). All four are worth committing; only the first is a result.
- **End-to-end speed is the measure of speed.** A number that prices
  the decomposition oracle, the solver, or the linear algebra alone is
  a stage diagnostic. `S` is the whole pipeline, cold, from setup to
  the recovered logarithm.

A worked example of all four, including a round where the conclusion
had to be withdrawn, is §14 of the ledger note.

---

## 8. What this framework does not do

Stated plainly, because a benchmarking harness that oversells itself is
worse than none:

- **The sizes are toy.** The largest instances here are tens of bits.
  Nothing measured is a statement about a deployed curve.
- **The engines, not the descent, are the ceiling on the algebraic
  rows, and F4 moved it.** The descent is symbolic and reaches 64
  boolean variables. Buchberger's basis computation stops deciding
  targets at twenty unknowns; `f4-f2` decides every two-summand target
  through twenty-eight (a degree-five matrix outgrows its 1 GiB cap at
  thirty), the matrix hybrids through thirty-four. `exhaustive`
  enumerates to 26 unknowns, `fes-f2` to 32, `fes-f2-wide` to 36, and
  `xl-f2` stops at 10. Ledger §17 has the measurements.
- **No engine here beats exhaustive search, and nothing beats rho.**
  In ledger §17 the F4-family engines cut the Gröbner row's whole-method
  `S` by `12×` to `1,535×`. Crossbred at its defaults crossed the scalar
  fast exhaustive search at 26–28 unknowns but not its vector form
  (`2.45`–`3.0×`). The inherited-F4 hybrid is `1.20×` the vector form at
  34 unknowns, with a crossing extrapolated near 35. The best whole
  row on every instance measured is still the pair table.
- **F5 ships as matrix-F5 inside a hybrid, not as a signature-based
  engine.** `matrix-f5` builds the Macaulay matrix to a fixed degree
  with the rows the F5 criterion predicts to reduce to zero left out,
  then propagates and splits. At its default degree 3 on the quadratic
  two-summand descents the criterion prunes only what linear equations
  allow — the trivial syzygies first appear at degree 4 — so there it
  tracks `matrix-f4`. An incremental signature-based F5 (or GVW, or a
  signature-based F4) is not in the registry; it is the obvious next
  engine to plug in, and §5 shows how.
- **No iterative matrix.** Two eliminations ship; Wiedemann and Lanczos
  are open, and the trait is written so that a matrix-vector product is
  a legitimate `work_unit`.
- **No algebraic oracle on prime-field curves.** The prime regime has
  only the table oracles (`subtract`, `mitm`), whose family law is
  `Θ(r^{1/6})` above rho. The one published algebraic mechanism is
  Petit–Kosters–Messeng's tower factor base; its design, and the test
  on the solver axis that decides whether to build it end to end, are in
  [`RESEARCH_PKM_TOWER_ORACLE.md`](https://github.com/aburan28/crypto/blob/main/research/notes/index-calculus/RESEARCH_PKM_TOWER_ORACLE.md).
  A pilot of that test (§10 there) found F4's solving degree nearly flat,
  where linear growth in `N` had been pre-registered: 4–5 for `m = 2`
  through `N = 18`, and 5–6 for `m = 3` through `N = 12`. Round 2 (§11)
  built the sparse tower-aware F4 that extending `N` needed
  (`src/cryptanalysis/f4_fp_tower.rs`, cross-checked against `f4_fp`). It
  finds the degree rising again, slowly:
  - at `m = 2`, to 6 at `N = 20` and still 6 at `N = 22`, in the Kummer and
    isogeny families alike and at every prime tried, which refutes the
    pilot's bounded-degree conjecture;
  - at `m = 3`, to 7 at `N = 15`.

  Whether the growth is linear or slower is open. So is `m = 4` past
  `N = 12`, the regime that decides the oracle. It ran out of memory at
  `N = 16`, where a diagnostic gives only `D ≥ 7`. No oracle is built.
- **No parallelism.** Every count is single-threaded, which is what
  makes operation counts comparable; a parallel implementation would
  need its own accounting.
- **The framework does not stop you reporting a stage as a speed.** It
  labels stage diagnostics and prints the whole-pipeline `S` beside
  them, but the discipline in §7 is yours to keep.

---

## 9. Reference: what ships

| stage | trait | plug-ins |
|:--|:--|:--|
| factor base | `FactorBaseBuilder` | `prime-abscissa`, `binary-subspace`, `koblitz-orbit` |
| targets | `Targets` | `random`, `walk` |
| point decomposition | `DecompositionOracle` | `subtract`, `mitm`, `mitm-frobenius`, `descent-algebraic` |
| polynomial solver | `SystemSolver` | `f4-f2`, `buchberger-f2`, `matrix-f4`, `matrix-f5`, `inherited-f4`, `crossbred-f2`, `xl-f2`, `sat-cdcl`, `fes-f2`, `fes-f2-wide`, `exhaustive` |
| relation matrix | `RelationSolver` | `incremental-gauss`, `structured-gauss` |

`ic bench --list` prints this with every parameter each plug-in reads.

### Source map

| file | what is in it |
|:--|:--|
| [`stages.rs`](../../src/cryptanalysis/ic_framework/stages.rs) | the traits and their types — the normative contracts |
| [`solvers.rs`](../../src/cryptanalysis/ic_framework/solvers.rs) | the `SystemSolver` adapters and their registry |
| [`pq_f4_f2.rs`](../../src/cryptanalysis/pq_f4_f2.rs) | the boolean F4 engine: pair selection and criteria, symbolic preprocessing, the packed elimination, solution extraction |
| [`koblitz_groebner.rs`](../../src/cryptanalysis/koblitz_groebner.rs), [`crossbred.rs`](../../src/cryptanalysis/crossbred.rs), [`mq_fes.rs`](../../src/cryptanalysis/mq_fes.rs) | the hybrid F4/F5 engines, crossbred, and fast exhaustive search the adapters call |
| [`ic_descent_degrees.rs`](../../src/cryptanalysis/ic_descent_degrees.rs), [`descent.rs`](../../src/bin/ic/descent.rs) | `ic descent`: the degree table, and the paired engine comparison (`--solver`) |
| [`plugins.rs`](../../src/cryptanalysis/ic_framework/plugins.rs) | the factor bases and decomposition oracles, the algebraic one included |
| [`pq_descent_symbolic.rs`](../../src/cryptanalysis/pq_descent_symbolic.rs) | the symbolic Weil descent the algebraic oracle builds its systems with |
| [`linalg.rs`](../../src/cryptanalysis/ic_framework/linalg.rs) | the structured elimination and the matrix registry |
| [`mod.rs`](../../src/cryptanalysis/ic_framework/mod.rs) | the runner and the report |
| [`bench.rs`](../../src/bin/ic/bench.rs) | the CLI |

The relation loop itself — the target guard, the collision guards, the
verification — is `collect_and_solve_with` in
[`ic_boundary.rs`](../../src/cryptanalysis/ic_boundary.rs), shared with
the boundary ledger rather than reimplemented, so a framework row is
comparable with a ledger row instead of merely similar to it.
