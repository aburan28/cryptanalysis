# ca-ic: the index-calculus research executable

The standalone `ca-ic` executable inspects elliptic-curve parameters and runs
bounded, reproducible index-calculus experiments on internally generated
known-answer or public hash-derived Koblitz targets. The `fixed` command also
accepts explicit K_0 curve parameters and points through degree 131, with durable
pair tables, relations and precomputation. See [Fixed parameters](FIXED_PARAMETERS.md).
The older inspection command uses imported points for mathematical validation.
The `prime` command runs the pipeline on prime-field curves by type — generic
(NIST P-192 … P-521), `j = 0` Koblitz-style (secp256k1) and `j = 1728` — see
[Prime-field curves](#prime-field-curves-ic-prime).

**Research provenance:** the per-stage scoreboard
([`BOUNDARY_TARGETS.md`](https://github.com/aburan28/crypto/blob/main/docs/ic/BOUNDARY_TARGETS.md)),
the frozen run records and the autolab control plane that produced them stay
in the upstream [crypto](https://github.com/aburan28/crypto) research
repository; this directory carries the tool, its parameter files and the
guide to running it.

## Commands

    cargo build --release --bin ca-ic
    ./target/release/ca-ic --help
    ./target/release/ca-ic list

A bare curve name is an inspection shortcut:

    ./target/release/ca-ic ecc2k-130
    ./target/release/ca-ic inspect --curve ecc2k-95 --json
    ./target/release/ca-ic inspect --curve secp256k1
    ./target/release/ca-ic p224
    ./target/release/ca-ic inspect --file docs/ic/prime-example.json

Named profiles are the binary challenges ECC2K-130, ECC2K-95 and sect163k1,
and every prime-field curve in the zoo: the SECG Koblitz (`j = 0`) curves
secp160k1, secp192k1, secp224k1 and secp256k1; NIST P-192, P-224, P-256,
P-384 and P-521 and the SECG secp112/128/160 `r` curves; Brainpool P192r1 …
P512r1; FRP256v1; SM2; and the GOST CryptoPro A/B/C and TC26 sets. `ic list`
prints them, and the standard aliases (`secp256r1`, `prime192v1`,
`sm2p256v1`, …) are accepted too. Their data comes from the repository's
ECC2K client definitions and existing curve constructors. ECC2K-130 has an
abstract normal-basis profile: the inspector checks its Koblitz group-order
recurrence but explicitly reports that the coordinate representation and
challenge points have not been imported. It does not substitute
polynomial-basis coordinates.

## Generated instances and larger synthetic curves

    ./target/release/ca-ic
    ./target/release/ca-ic --solver sat
    ./target/release/ca-ic run --degree 11 --curve-a 1 --known-log 53 --solver enumerate
    ./target/release/ca-ic run --degree 9 --random-target --seed 42 --json
    ./target/release/ca-ic run --degree 13 --curve-a 0 --solver pair-table --summands 3

The default run uses K_0 over GF(2^9) and known logarithm 53. The solver
constructs the target from the declared known answer, then checks both the
recovered value and the group identity. No public point file can be passed
to the run command.

The staged `workflow` command also accepts a scalar-blind public target:

```json
{"targets":[{"public_hash_seed":29}]}
```

This form hashes the curve identity, seed, and counter to an abscissa,
chooses a lift from the next digest bit, and applies the public cofactor.
It constructs and records no target scalar. Both individual descent and
the signed-Frobenius rho baseline accept a recovered value only after
checking `[d]G = Q`. The older `known_log` and `random_seed` forms retain
their expected-scalar check as an additional known-answer control.

The following knobs are recorded in each run report:

- degree: the field degree n; odd values 3 through 63 for the Koblitz
  family (a curve is usable only when its largest prime factor exceeds
  the cofactor, which above 23 holds for degrees 29 (curve-a 1), 31, 37,
  and 39 (curve-a 0)), or k times an odd number for a subfield curve;
- curve-a: 0 or 1, with b fixed to 1, for a Koblitz curve; the
  coordinate of a in the subfield basis otherwise;
- subfield: the degree k of the subfield the curve is defined over,
  q = 2^k (default 1, the Koblitz family; up to 8), see below;
- curve-b: the coordinate of b in the subfield basis (default 1);
- known-log: a positive scalar smaller than the selected subgroup order;
- random-target: draw a known-answer scalar reproducibly from seed;
- seed: seed for the generated fixture and relation sampler;
- factor-index: candidate in the legacy degree-ord_n(2) factor family;
- factor-base: a recipe file written by `ic search`, replacing factor-index;
- summands: factor-base points per relation, 2 (default), 3, or 4;
- max-trials: 1 through 1000000;
- solver: groebner, sat, enumerate, pair-table, wdsat, or mq-fes;
- batch: targets decomposed per parallel batch (0 = CPU count);
- control: legacy accounting, see below.

Solvers answer the same question, "is this target a sum of `summands`
factor-base points", and every returned decomposition is re-added in the
group before it becomes a relation:

- enumerate: ordered-tuple search, `|F|^(m-1)` group operations per target;
- pair-table: meet in the middle over a table of all `|F|(|F|+1)/2` pair
  sums built once per run — one lookup per target for two summands,
  `|F|` for three, `|F|²` for four (16 bytes per table entry);
- groebner: the Weil-restricted Semaev system reduced by matrix-F4;
- sat: the same system, CDCL with native parity rows;
- wdsat: the same Semaev system emitted as Trimoska ANF and solved by an
  external WDSat binary (`--wdsat-binary PATH`). See
  [`RESEARCH_WDSAT_IC_UNIFICATION.md`](https://github.com/aburan28/crypto/blob/main/research/notes/ecc2k130/RESEARCH_WDSAT_IC_UNIFICATION.md).
  Requires a capacity-sufficient build of
  [`mtrimoska/WDSat`](https://github.com/mtrimoska/WDSat); the frozen
  baseline builder is
  the upstream `research/index_calculus_baseline_20260914/pilot/build_pilot.py`.
- mq-fes: ALMASTY/libfes-inspired quadratic Semaev solver (`m = 2` only) —
  libfes FFS Gray (`L=4` unroll) for early-exit `find_one`, Möbius for
  all-roots when `n ≤ 24`, Monica hybrid past that
  (<https://gitlab.lip6.fr/almasty/mq>,
  <https://github.com/cbouilla/libfes-lite>).

Not every degree/coefficient combination has a usable subgroup. A valid
curve does not guarantee successful collection or an invertible relation
system. Factor-base materialization is capped at 4096 abscissae
(dimension 12 for the legacy family). Fixture generation and inspection do
not require a usable factor base.

The run display follows factor-base construction, an optional pair table,
relation collection, linear algebra, and verification. By default relation
columns are signed Frobenius orbits merged by their cofactor projection, the
relation matrix is kept in reduced echelon form over Z/rZ as relations
arrive, and the run stops the moment the scalar is pinned — dependent
relations are counted, never padded. An inconsistent relation or a pinned
scalar that fails `[d]G = Q` invalidates the run outright. `--control`
restores the earlier accounting for matched comparisons: one column per
Frobenius orbit, no projection merge, a fixed surplus of relations, and a
single solve at the end. Incomplete results exit unsuccessfully and remain
incomplete in JSON reports.

### Subfield curves beyond the Koblitz family

    ./target/release/ca-ic run --degree 14 --subfield 2 --curve-a 0 --curve-b 2 --solver pair-table
    ./target/release/ca-ic search --degree 22 --subfield 2 --curve-a 1 --curve-b 3 --family divisor
    ./target/release/ca-ic logs --degree 14 --subfield 2 --curve-a 0 --curve-b 2 --database logs14.json

The Galbraith–Granger–Merz–Petit construction needs only that the curve
be defined over a subfield: with `--subfield k` the synthetic curve is
`y² + xy = x³ + a x² + b` with `a, b ∈ GF(2^k) ⊂ GF(2^n)`, `n = k · e`
and `e` odd, and the `2^k`-power Frobenius `π` plays the role squaring
plays on a Koblitz curve. `a` and `b` are named by their coordinates in
an `F_2`-basis of the subfield (the kernel of `X^{2^k} + X`), so
`--subfield 1 --curve-a a --curve-b 1` is exactly `K_a`. Point counting
goes through `#E(GF(2^k))`, found by enumeration, and the trace
recurrence `s_i = t·s_{i−1} − q·s_{i−2}`; `λ` is the root of
`λ² − tλ + q` with `π(G) = [λ]G`.

The invariant factor bases are the kernels of `q`-linearised
polynomials `Σ c_i X^{q^i}` with `c_i ∈ GF(q)`, classified by the
irreducible factors of `x^e − 1` over `GF(q)` (Cantor–Zassenhaus over
`GF(q)`, carried out inside `GF(2^n)`); a factor of degree `d` gives a
subspace of `2^{kd}` abscissae whose points fall into orbits of length
dividing `e`. Recipe indices refer to that factor list, which for `k = 1`
is the familiar `F_2` list in the same order, so every Koblitz recipe,
document and report is unchanged. Documents record `subfield` and
`curve_b` (omitted when 1) and are bound to them. Two things differ
from the Koblitz case in practice: an even `n` is allowed (the
Artin–Schreier solve for even degree is a linear solve, not the
half-trace), and when `x^e − 1` splits into binomials `x^d − c` over
`GF(q)` the invariant subspaces are multiplicative cosets whose
inverses land in the reciprocal factor's subspace, so a curve with
`Tr(a) = 1` and `b = 1` has no points over them at all — the search
scores such bases at zero and a run over one reports a base with no
usable columns, so pick `b` (or `a`) accordingly, as the examples above
do.

## Searching for a factor base

    ./target/release/ca-ic search --degree 15 --curve-a 1 --spec-out fb15.json
    ./target/release/ca-ic run --degree 15 --curve-a 1 --factor-base fb15.json --solver pair-table
    ./target/release/ca-ic search --degree 31 --curve-a 0 --summands 3 --family divisor --max-dimension 11

`search` scores factor bases by the number the pipeline actually pays for:
the expected trials to collect a determining system,
`(columns + 1 + extra) / coverage`, where coverage is the fraction of
subgroup targets that decompose into `summands` base points. Coverage is
measured exactly on one shared target set — the whole subgroup when
`r − 1 ≤ --exhaustive-cap` (default 4096), otherwise `--targets` seeded
samples — by enumerating every witness of every target through the pair
table. Candidates come from three families:

- factor: the legacy single irreducible factors (`--factor-index`);
- divisor: every product of irreducible factors of `x^n − 1` whose degree
  lies in `[--min-dimension, --max-dimension]`, the complete list of
  Frobenius-stable linear subspaces;
- union: Frobenius closures of random seed spaces of dimension
  `--union-min-seed` to `--union-max-seed`, `--union-samples` per dimension
  plus the standard basis.

Each candidate is also tried after 2-torsion saturation (when the cofactor
is even; `--no-saturate` skips it) and after greedy orbit pruning
(`--no-prune` skips it): signed orbits are dropped while doing so lowers the
expected trial count, which is an exact recount over the witness list
rather than a re-search. The pruned base stays Frobenius- and
negation-closed, so every relation identity survives.

### Ranking by what the solver pays, not by trials alone

Expected trials is half the collection cost. A trial is paid whether or not
it succeeds, so collection spends `trials × (cost per trial)`, and the
second factor is the one that varies: coverage saturates at 100% as the
subspace grows while the Weil-restricted summation system keeps `m·ℓ`
Boolean unknowns. At `K_1/2^15` the two orders disagree by `22.41×` over
twelve verified logarithms — see
[`research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md`](https://github.com/aburan28/crypto/blob/main/research/notes/index-calculus/RESEARCH_FACTOR_BASE_SOLVE_COST.md).

    ./target/release/ca-ic search --degree 15 --curve-a 1 --summands 2 --family divisor \
        --min-dimension 3 --max-dimension 8 --no-prune --no-saturate \
        --solver groebner --solve-cost-targets 8

`--solve-cost-targets N` runs the Gröbner oracle on `N` census targets per
candidate, charging refutations as well as successes, and ranks by
`expected_stage_ops = expected trials × measured word XORs per target`. The
report's `scoring_objective` says which of the two ranked it, and each
candidate carries `measured_ops_per_target`, `expected_stage_ops` and
`trace_zero`. Omitted, nothing changes: the ranking is the trial count as
before.

Three restrictions, each refused loudly rather than silently worked around,
because a number that does not describe the run is worse than no number:

- it prices the **Gröbner** oracle, so `--solver` must be `groebner` —
  scoring one oracle and running another selects for the wrong thing;
- only a **linear-subspace** candidate is described by its own system. The
  restriction is written over the subspace basis, so a pruned, saturated,
  union or orbit base — a proper subset of that span, carried by the SAT
  domain trie instead — would be priced on the span rather than on itself,
  at a cost in time of several orders of magnitude. Such candidates are
  left unpriced with the reason in `solve_cost_skipped`, and ranked below
  every priced one, since trials and word XORs are not comparable numbers;
- nothing is measured while `IC_REDUCTION_CACHE` is set, where a memoised
  reduction returns without running F4 and the counter diff would report
  replayed work as free. (A preprocessing hit is harmless: F4 still runs,
  so it is still counted.)

Free and unmeasured, reported for every candidate: `trace_zero`, true when
the abscissae lie in `ker Tr`, which doubles the yield and is decided by the
divisibility `(x+1) ∤ g` rather than by solving anything.

The best `--validate-top` candidates are then validated by real child runs
on `--holdout` fresh known-answer fixtures with `--solver` (default
pair-table); the selected candidate is the fastest one that verified every
holdout. `--spec-out` saves its recipe, a small JSON document bound to the
degree and coefficient it was found on, which `run --factor-base` replays.
Status is `complete` only with a validated winner; `--validate-top 0`
reports `unvalidated` with the census ranking alone.

The census is exact on its target set and ignores per-trial oracle cost;
the report carries `enumeration_ops_per_trial`, `pair_table_lookups_per_trial`
and `sat_variables` as cost proxies, and the validation runs measure the
wall time that combines both. A selected candidate is the best validated
observation on these fixtures, not a global optimum.

Why this matters: `ic run --degree 15 --curve-a 1` with the legacy family
collects no relation at all in 20 000 trials — the 31-point base never
reaches the order-211 subgroup with two summands — while the search finds,
scores and validates bases covering all 210 targets in a few seconds.

## Factor-base logarithms and individual-logarithm descent

    ./target/release/ca-ic logs --degree 9 --curve-a 0 --solver pair-table --database logs9.json
    ./target/release/ca-ic solve --degree 9 --curve-a 0 --logs logs9.json --known-log 53
    ./target/release/ca-ic logs --degree 31 --curve-a 0 --summands 3 --factor-base fb31.json --database logs31.json
    ./target/release/ca-ic solve --degree 31 --curve-a 0 --summands 3 --logs logs31.json --random-target --seed 7

Like a number-field-sieve pipeline, `ic` separates the two costs the
plain `run` conflates. `run` bakes the target into every relation
(`R = [a]G + [b]Q`) and rebuilds the whole relation matrix per target.
Instead:

- `ic logs` **precomputes**, once per curve and factor base, the
  discrete logarithm of every relation column — the factor-base
  logarithm database. It draws `R = [a]G` probes (no target), decomposes
  each over the factor base, rewrites it as `Σ_o c_o x_o ≡ h·a (mod r)`
  over the projected columns, and once the rows determine every column
  reads the whole logarithm vector off in one solve. Every column log is
  certified by `[x_o]G == R_o` before the database is written; a
  database that fails that check is never emitted.
- `ic solve` **descends** a target with a single relation, reusing the
  database. It draws `R = [a]G + [b]Q` until one decomposes, giving
  `h·a + h·b·d ≡ Σ_o c_o x_o (mod r)`; with the column logs known, the
  scalar `d = log_G Q` falls out of one modular inverse, and the
  recovered `d` is re-checked as `[d]G == Q` before it is returned. On
  load the whole database is re-verified against the reconstructed curve,
  so a tampered or mismatched database is rejected, not trusted.

The database is a JSON document bound to its degree, coefficient,
subgroup order and factor-base spec; `solve` rejects it on any other
curve. Only the projected column representation is used (the `ic`
default): its columns are canonical cofactor projections `R_o ∈ ⟨G⟩`, so
each column logarithm is a genuine, self-certifying discrete log.

The precomputation reaches whatever the factor base and summand count
support. On `K_0/2^31` over a search-selected dimension-11 base
(`--summands 3`, 35 columns) it completes in about 15 s; each subsequent
target then needs one or two relations. The `logs` trial budget
(`--max-trials`, default 200000) bounds the search for a full-rank
relation set; a base whose coverage cannot determine every column
reports `incomplete` rather than emitting an unverified database.

### Linear algebra: relation filtering and block Wiedemann

    ./target/release/ca-ic logs --degree 31 --curve-a 0 --summands 3 --factor-base fb31.json --database logs31.json --linear-algebra sparse --block-size 4
    ./target/release/ca-ic logs --degree 31 --curve-a 0 --summands 3 --factor-base fb31.json --database logs31.json --linear-algebra dense

Each relation has at most `m` nonzero entries, so the relation matrix is
sparse in exactly the way a number-field-sieve matrix is. By default
(`--linear-algebra sparse`) `ic logs` solves it the way CADO-NFS does:

1. **Filtering** — duplicate rows are dropped; a column occurring in only
   one row (a *singleton*) is removed with that row and recovered later
   by back-substitution; surplus rows beyond a small excess are removed,
   choosing rows whose removal cascades through the weight-2 columns
   (the clique rule); light columns are merged away by structured
   Gaussian elimination under a fill-in bound. Every elimination is
   recorded, so the eliminated logarithms are reconstructed exactly from
   the core solution (back-substitution, then propagation through the
   original rows, then a small dense residual if anything is left).
2. **Block Wiedemann** — the reduced core is made square by folding its
   excess rows into random earlier rows, homogenised to `M (x, 1)ᵀ = 0`,
   and a kernel vector is read off the Krylov sequence `X Mⁱ Y` of
   `block_size × block_size` blocks through a matrix Berlekamp–Massey
   step (a shifted minimal approximant basis). Only sparse
   matrix-times-block products touch the matrix, in parallel over rows.

The sparse path never attempts a solve before every column occurs in
some row, and the solution is checked against every relation before
the group certification `[x_o]G == R_o` runs. `--linear-algebra dense`
keeps the reference behaviour: full big-integer elimination after every
new relation. Both paths certify the same database (the `ic` tests
compare them); the report's `linear_algebra` object records the mode,
the attempts, the time, and for the sparse path the filtering counts
and the Wiedemann run (`core_dimension`, `sequence_length`, products).

## Running the pipeline as a resumable workflow

    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31
    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31 --stop-after logs
    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31          # resumes

Like a number-field-sieve run, `ic workflow` executes the pipeline as
stages whose outputs live on disk, so a run can be stopped, inspected
and resumed without redoing finished work:

1. **select** — the factor base, either an explicit recipe or the
   best-by-census candidate of the factor-base search; written as
   `factor_base.json`.
2. **collect** — relations, in work units (see below); each unit is
   written as `relations/unit-NNNNN.json`.
3. **logs** — the units are merged, every relation re-verified in the
   group and deduplicated, and the factor-base logarithm database solved
   (`logs.json`), every column certified by `[x]G == R`. If the
   relations do not yet determine every column, further units are
   collected up to `collection.max_units`.
4. **solve** — each target descended with one relation reusing the
   database; `solutions.json` is rewritten after every target, so an
   interrupted run resumes at the first unsolved one. The pair table is
   built once per process and shared by collection and descent.

`state.json` records a BLAKE3 digest of the parameter file and each
stage's status. A rerun in the same directory reloads existing
artifacts, re-verifies them against the reconstructed curve (a stale or
tampered artifact is an error, never trusted), and continues from the
first incomplete stage; a parameter file whose digest differs is refused
so one directory never mixes two experiments. Artifacts are written
atomically. `--stop-after select|collect|logs|solve` ends the run early.

### Distributed relation collection

    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31 --collect-units 0-3    # worker A
    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31 --collect-units 4-7    # worker B
    ./target/release/ca-ic workflow --params wf.json --dir runs/k0n31                        # merge, solve, descend

Relation collection is embarrassingly parallel, and the workflow splits
it the way a sieve is split into `q`-ranges. The probe scalar of trial
`t` depends only on the parameter seed and `t`, so the probe sequence
is one fixed, reproducible sequence; a **work unit** `k` is the slice
`[k · unit_trials, (k + 1) · unit_trials)` of it. Any process with the
parameter file (and `factor_base.json`, when the base came from the
search) can run a set of units with `--collect-units` — it writes
`relations/unit-NNNNN.json` for each and stops — and the files from
several workers or machines are simply placed in the run directory. The
driver without `--collect-units` collects whatever units of the first
`collection.units` are still missing itself, then merges everything
present. Inside a unit the trials run in parallel over the cores.

A unit costs what its trials cost and nothing more: the collector — whose
point index map is keyed by big integers and takes about as long to build
as a short unit takes to run — is built once for the whole stage rather
than once per unit, so splitting the same work into eight units instead
of one no longer adds to the bill.

Two setup costs alongside it were the same shape. Selecting a subgroup
base rebuilt the whole base after every batch of eight abscissae, which
is quadratic in the abscissae; it now skips the rebuilds that could only
have come back short, since an abscissa carries at most two points. And
the projected signed-orbit map — every base point multiplied by the
cofactor, then each one's whole Frobenius orbit walked — ran in
big-integer arithmetic; it now runs in single words where the field fits,
which it does for every degree this pipeline reaches. At degree 53 on a
15264-point base, selecting goes from 8.60 s to 0.94 s and the orbit map
from 8.16 s to 0.048 s, and the base and its columns are unchanged. The
pair table's 6.7 s is real `|F|²/2` work and is untouched; it is now the
dominant fixed cost, and unlike the scanning it does not grow with `r`.

A relation file carries only the probe scalar and the factor-base point
indices of each relation, bound to the parameter digest, curve, factor
base and summand count. On merge every relation is re-verified in the
group (`[a]G == Σ P_i`, exactly `m` indices, all in range) and exact
duplicates are dropped, so a corrupt or forged file cannot poison the
database — a rejected relation is counted, never used — and a file from
another run or base is ignored, not merged. Partition invariance is
tested: the union of any set of units equals the relations of a
single-process run over the same range, and `ic logs` itself now draws
its probes from the same sequence in parallel batches.

Parameters (`collection`, all optional):

    "collection":{"unit_trials":4096,"units":4,"max_units":64}

`unit_trials` probes per unit; `units` the number the driver collects
before the first solve; `max_units` the most it may collect when the
relations do not yet determine every column. The report's collect stage
lists the units present, run and ignored; the logs stage reports the
relations loaded, rejected and deduplicated and which units were used.

A parameter file (schema_version 1):

    {"schema_version":1,"name":"k0n31","curve":{"degree":31,"curve_a":0},
     "summands":3,"solver":"pair_table","seed":1,"max_trials":200000,
     "linear_algebra":{"mode":"sparse",
                       "sparse":{"wiedemann":{"block_m":4,"block_n":4},
                                 "filter":{"target_excess":32,"merge_max_weight":8}}},
     "collection":{"unit_trials":4096,"units":4,"max_units":64},
     "factor_base":{"mode":"search","family":"divisor","min_dimension":5,
                    "max_dimension":11,"targets":256,"saturate":false},
     "targets":[{"known_log":"654009"},{"random_seed":7},{"random_seed":8}]}

The `search` mode also takes `solve_cost_targets`, the workflow form of
`--solve-cost-targets` above: with it the select stage ranks candidates by
measured solving cost instead of by expected trials. It requires
`solver: "groebner"`, `prune: false`, `saturate: false` and a `factor` or
`divisor` family, for the reasons given there, and the run is refused if
they disagree.

`factor_base.mode` is `spec` (with a recipe as written by `ic search`)
or `search` (the census search's knobs; the best candidate is taken
without child validation). Each target is a synthetic known-answer
instance: `known_log` names the scalar, `random_seed` draws one
reproducibly. Solver is `pair_table` (default), `enumerate`, `groebner`
or `sat`. `linear_algebra` is optional: `mode` is `sparse` (default;
filtering + block Wiedemann, with every knob of the sparse solver under
`sparse`) or `dense`. `collection` sizes the work units (above). The
report lists every stage with whether it ran or was reused — the collect
stage with its units, the logs stage with its verification counts and
linear-algebra statistics — and every solution with its expected and
recovered scalar.

### The ρ baseline (`vs_rho`)

    "baseline":{"rho":true,"rho_seed":5931241263826122831,"rho_max_iterations":268435456}

With `baseline.rho` the driver runs the signed-Frobenius Pollard ρ
(`koblitz_signed_frobenius_rho_with_progress`, which already carries the
Koblitz automorphism discount: it walks the `A = 2n` classes) on the
same known-answer targets, in the same process, after the descent, and
writes `baseline.json` plus a `vs_rho` block in the report with the
three timing classes the boundary ledger distinguishes:

- **charged** — per-target descent wall (one decomposition and a lookup
  against the reused database) against the ρ walk on the same target;
- **amortised** — select + collect + logs + pair-table wall divided over
  the targets, plus the descent;
- **whole process** — the precompute counted once against the ρ total.

Each comes with the ratio `ρ / IC` and a boolean verdict; a verdict is
`true` only when every target was solved *and* ρ-verified. The ledger's
`vs_rho` row asks for exactly these fields (`timing_class`,
`automorphism_discount`, both costs, `claim_boundary`); the report
carries them, but promoting a row still goes through the ledger's own
autolab and independent-replay process.

The baseline is a real opponent, not a formality, so read it first:

- It walks the `A = 2n` signed Frobenius classes, by the
  distinguished-point method — a direct-mapped cache of recent points
  for the short cycles, a sparse table of stored points for the
  long-range collision.
- Fruitless cycles (a cycle whose jumps cancel, which the negation map
  makes common) are escaped by doubling the cycle's own smallest state,
  so the walk stays a deterministic map. `charges.fruitless_cycles`
  counts them.
- Walks are stepped in batches sharing one field inversion
  (`parallel_walks`, default 32, scaled down on instances whose whole
  walk is shorter than the setup would cost).
- Its step count tracks `√(πr/2) / √(2n)`; a run far above that is a
  broken baseline, and a `vs_rho` verdict built on one means nothing.
  `rho.verified` must equal the target count — **a ρ that fails to
  recover its logarithms makes every ratio in the block meaningless**,
  which is exactly how an earlier revision of this baseline produced a
  spurious charged crossover at `n = 41`.

### Choosing a factor base

Five families are recipes (`ic search --family`): `factor`, `divisor`
and `union` are linear — an invariant subspace, a divisor of `x^e − 1`,
or a union of Frobenius translates of a seed span — and `subgroup` is
not. The linear families exist because the algebraic oracles need them:
Semaev's polynomials and the Weil descent are written over a subspace.
The pair-table oracle is a meet-in-the-middle search and needs no
structure at all, and for it the structure is a cost, not a feature.

`subgroup` draws abscissae pseudo-randomly and keeps `[h]P` for the
cofactor `h`, so every base point lies in the prime-order subgroup the
targets live in. Sums of such points cannot leave that subgroup, and the
measured decomposition rate lands on the `|F|³/(3!·r)` a random base
would give — at degree 41, one target in 28 against one in 273 for the
subspace union of the same size, with the same column count. Selection
uses no logarithm: `[h]P` is in the subgroup whatever `P` is.

Use it with the pair-table solver. `groebner` and `sat` need a linear
domain and will refuse.

**How big?** With a subgroup base the work per target falls as
`r/|F|²` — four times cheaper per doubling — while the pair table grows
as `|F|²`, so the answer depends on how many targets share the database.
At degree 41: 5248 points costs 3.0 s of precompute and 16.2 ms a
target, 10496 points costs 9.0 s and 7.2 ms, and the two cross at about
665 targets. `docs/ic/runs/koblitz-base-size-20260912.json` has the
sweep and both end-to-end runs. Past about 10500 points at that degree
the decomposition rate saturates and further growth only makes each
trial dearer.

`PairSumTable::build` keeps a base inside 4 GiB, and past that budget it
changes representation rather than refusing. The full table stores each
pair as `(packed sum, i, j)`, sixteen bytes; the **compact** one stores a
bucketed hash of the sum in a `u32` — never a false negative, a false
positive about one time in `2²⁸` — and recovers the summands of a hit by
one `|F|`-long scan, since `target − P_i` is a base point exactly when
`i` is a summand. That scan asks the group rather than the table, so a
false positive costs an empty scan and never a wrong answer. Hits are
rare, so it is paid about once per relation rather than once per probe.

At a fixed budget `B` the base is `|F| = √(2B / bytes per pair)`, and the
descent needs `2r/|F|²` probes, so the width of a stored pair is
proportional to the descent's cost. Four and a half bytes instead of
sixteen is a base of 42302 points instead of 23169 at 4 GiB, and 3.3
times fewer probes. Below the budget nothing changes: a base that fits
with its summands keeps them. Below even the compact size the build
still refuses with a number instead of an allocation.

`docs/ic/runs/koblitz-reach-versus-memory-20260912.json` collapses the
cost laws into reach against memory, and then tests them at three
factor-base widths on one degree. The probe-count law `2r/|F|²` is
confirmed to within 1.5%; what is not confirmed is the assumption beside
it, that a probe costs the same whatever the table size. It does not — a
probe is a random access into a table quadratic in `|F|`, and it measured
0.148 µs into 0.2 GB against 0.249 µs into 3 GB. The reach therefore
grows as **`M^1.64`**, not `M²`: 1.64 bits a doubling of memory, and at
80 bits 576 TiB rather than 64. Read the file's
`the_exponent_is_an_upper_bound` before quoting any of it — 0.40 was
fitted entirely inside DRAM, and the law's whole purpose is to push the
table out of it.

`docs/ic/params/k0n61-subgroup-wide.json` is the largest rung this family
offers: `K_0/F_{2^61}`, a 48-bit subgroup, `r = 162 888 033 982 417`, on
a 36112-point compact base. It solves 32 of 32 with a 53.1 ms descent
against ρ's 3.248 s — charged 61.2, amortised 1.29, and all three
verdicts true at 32 targets.
`docs/ic/runs/koblitz-degree61-20260912.json` records it, and says what
it does to the earlier reach projection: that projection put the charged
ratio at 5.1 at 48 bits and wanted 315 targets, because it was measured
on constants that have since moved three times.

`docs/ic/params/k0n53-subgroup-wide.json` is the degree-53 rung on a
36464-point compact base: the descent falls from 50.4 ms a target to
16.3 ms and the charged ρ/IC ratio rises from 25.0 to 75.2, while the
precompute rises from 16.5 s to 87.8 s. That is a trade, and
`docs/ic/runs/koblitz-compact-pair-table-20260912.json` prices it — about
2200 targets before the wider base is the cheaper one.

**`descent_summands`** lets the descent ask for a different number of
summands than collection, which shares only the base and its pair table.
Collection wants few probes (each costs two scalar multiplications) so
it takes three; the descent walks its probes by `+G` in blocks sharing
one inversion, which makes a probe cheaper than the lookup after it, so
two wins. At degree 41 that is 14.35 ms a target against 8.63 on a
5248-point base, and 7.20 against 4.65 on a 10496-point one.

### Ledger rungs, ready to run

`docs/ic/params/k0n{31,37,39,41}.json` are the four Koblitz rungs of the
boundary ledger as parameter files — 32 known-answer targets each, the
ρ baseline on, collection units sized to the base:

    ./target/release/ca-ic workflow --params docs/ic/params/k0n41.json --dir /tmp/n41

`docs/ic/params/k0n53-subgroup.json` is the largest subgroup this family
offers (44 bits, 38× the degree-41 rung). It solves 32 of 32 with a
49 ms descent against ρ's 1.216 s, and
`docs/ic/runs/koblitz-degree53-and-reach-20260912.json` carries it
together with the projection of where the advantage runs out: the
charged class survives to about a 52-bit subgroup, and the whole-process
class needs a batch of targets that grows with `r` (16 at 40 bits, 96 at
45, 834 at 50). Relation collection is what stops it, not the descent.

`docs/ic/params/k0n{31,37,39,41}-subgroup.json` are the same four rungs
with subgroup bases; `docs/ic/runs/koblitz-subgroup-bases-20260912.json`
records them, and the charged ρ/IC ratio there crosses 1 at degrees 37,
39 and 41 (8.3 at 41). Read that file's `what_this_is_not` before
quoting it — in particular, its degree-41 whole-process verdict is a
bulk statement about 32 targets, not a single-instance one.

`docs/ic/runs/koblitz-scaling-20260911.json` records two consecutive
series of all four, with per-stage timings, filter and Wiedemann
statistics, and both ρ and IC verification counts. No rung crosses: the
charged ρ/IC ratio is below 1 at every one. Read its
`what_this_is_not` before quoting any number from it.

## Prime-field curves: `ic prime`

    ./target/release/ca-ic prime --curve secp256k1 --bits 28
    ./target/release/ca-ic prime --curve p224 --bits 24 --targets 64 --width 4
    ./target/release/ca-ic prime --type j1728 --bits 24 --json
    ./target/release/ca-ic prime --curve secp256k1 --bits 16 --solver semaev

The binary pipeline gets its speed-up from a factor base closed under
Frobenius. A prime field has no Frobenius acting on the points, but some
prime-field curves have **automorphisms** that play the same role, and the
curve type decides which:

| type | deployed curves | `Aut(E)` on `⟨G⟩` | action on `(x, y)` | eigenvalue on `⟨G⟩` |
|---|---|---|---|---|
| `generic` | P-192 … P-521, secp`r1`, Brainpool, FRP256v1, SM2, GOST | `{±1}`, `w = 2` | `(x, ±y)` | `±1` |
| `j0` (`koblitz`), `p ≡ 1 (3)` | secp160k1, secp192k1, secp224k1, secp256k1 | `μ₆`, `w = 6` | `(ζᵏx, ±y)` | `±λᵏ`, `λ² + λ + 1 ≡ 0` (GLV) |
| `j1728`, `p ≡ 1 (4)` | none in the zoo | `μ₄`, `w = 4` | `ιᵏ`, `ι(x, y) = (−x, iy)` | `μᵏ`, `μ² ≡ −1` |

A factor base that is a union of `m` whole `Aut`-orbits has `w·m` points but
only `m` unknowns: every orbit member's logarithm is `e(α)·log(rep)`. A
decomposition `R = α(P_o) + β(P_o')` through *any* orbit members is a relation
`e(α) x_o + e(β) x_o' ≡ log R`, so against a negation-only base the same
unknowns cover `(w/2)²` times as many pair sums — 9× on a `j = 0` curve. That
is the prime-field analogue of the GGMP Frobenius collapse.

**The older `j = 0` module does not do this.**
`ec_index_calculus_j0::find_relation_with_psi` keeps one representative per
`ζ`-orbit, but a decomposition through a `ζ`-image is looked up to its orbit
and then discarded by `resolve_signs`, which tries only the stored
representative. Its orbits therefore add factor-base size, not coverage. The
new pipeline uses the whole orbit; on one `j = 0` curve with the same unknowns
it yields over 5× the relations of the `{±1}` control
(`the_extra_automorphisms_multiply_the_yield`).

### What a run does

With `--curve NAME` the report first carries a **structural** block on the
real curve, `named_curve`, computed on its parameters and never solved: type,
`j`-invariant, `|Aut|`, the cube root of unity `ζ`, the GLV eigenvalue `λ`
checked as `ψ(G) = [λ]G`, whether Semaev's `S₃` is `ζ`-equivariant (checked
on samples), and `log2` of the rho cost with and without the `√w` fold. For
secp256k1 that is `|Aut| = 6`, rho `≈ 2^128.3`, folded `2^127.0`.

Then the pipeline runs on a **scaled-down curve of the same shape**:

1. **Shape.** A coefficient that is small, or `p − small`, is kept, and a
   random-looking one is redrawn: secp256k1 scales to `y² = x³ + 7`,
   P-224 to `y² = x³ − 3x + b` with `b` random, Brainpool to random `a, b`.
   The prime is drawn in `[2^{bits−1}, 2^bits)` in the class the type's
   automorphisms need, and the cofactor may not exceed the named curve's
   (`j = 1728` always carries the rational 2-torsion point `(0, 0)`, so it
   gets cofactor ≤ 4).
2. **Certified order.** A baby-step giant-step over the Hasse interval finds
   `N` with `[N]P = O`, and `N = h·r` with `r` prime, wider than the
   interval, and `[h]P ≠ O` proves `#E = N`: `r | ord(P)`, so `N` is the only
   multiple of `ord(P)` in the interval. The generator is `[h]P`. The report's
   `instance.order_certificate` records the interval and the BSGS steps.
3. **Automorphisms.** The table above is built and every eigenvalue is
   checked on `G`.
4. **Factor base.** Abscissae are drawn pseudo-randomly, lifted, multiplied
   by the cofactor into `⟨G⟩`, and one representative per orbit is kept. No
   logarithm is used. `--orbits N` fixes the count; otherwise it is
   `--width · √r / w`.
5. **Relations.** Probes `R = [a]G` are walked by `+[s]G` (one addition a
   probe). The oracle sweeps `α⁻¹(R) − P_o` over every automorphism and every
   representative, one batched inversion per block, looks the difference up
   by abscissa, and stops at the first hit; the sweep's starting point is
   rotated by the probe so that a wide base's relations do not pile onto its
   first columns. Every hit is re-added in the group before it is kept.
6. **Logarithms.** Each relation has at most two unknowns, so the system is a
   gain graph and is solved exactly, component by component: a spanning tree
   expresses every column affinely in the root, and a cycle of gain `≠ 1`, or
   a one-term relation, pins it. Every solved column is certified by
   `[x_o]G == P_o`; an uncertified column would never be used, and the report
   counts rejected relations, uncertified columns and inconsistent components
   (all three must be zero for a `complete` run).
7. **Descent and baseline.** Each of `--targets` known answers (the planted
   `--known-log`, default 53, then logarithms drawn from `--seed`) is
   recovered from one decomposition of `R = [a]G + [b]Q` over the certified
   orbits and checked as `[d]G == Q`. The rho baseline is 32 r-adding walks
   sharing one inversion per step, with distinguished points, in the same
   arithmetic; it does not fold by `Aut`, and the analytic folded expectation
   `√(πr/2)/√w` is reported beside it.

Everything is seeded: a rerun with the same arguments reproduces every
operation count (`runs_are_reproducible`).

### What it costs, and how to read `vs_rho`

Counts are group operations — affine additions, each sharing a batched
inversion on both sides — so they compare across implementations. The
three ratios are the binary block's timing classes, as `rho / IC` (above 1
means index calculus spent less): **charged** (one descent, database paid),
with a second charged ratio against the folded-rho expectation;
**amortised** (precompute spread over the targets, plus descent); and
**whole process**.

A random point has `≈ (wm)²/(2r)` decompositions, and the sweep finds each
twice (once per summand) and stops at the first. So the precompute is
`≈ c·r/w` whatever the width — linear in `r` — while one descent is
`≈ wm·(P₀ + Σ_{D≥1} P(D)/(2D+1))/(1 − P₀)` for `D ~ Poisson((wm)²/(2r))`,
about `√r / width` once the base is wide. Over 256 targets at 28 bits the
measured mean descent is within 2.5% of that formula for both generic and
`j = 0` curves.

`cargo run --release --example prime_ic_by_curve_type -- 16 28 32`, width 2,
32 targets per database, every target recovered by both sides:

| type | `\|Aut\|` | bits | precompute | mean descent | mean rho | folded rho | charged | whole process |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| generic | 2 | 20 | 5.84e5 | 665 | 624 | 651 | 0.94 | 0.033 |
| generic | 2 | 24 | 9.75e6 | 2022 | 3427 | 2602 | 1.69 | 0.011 |
| generic | 2 | 28 | 2.22e8 | 12540 | 19510 | 12530 | 1.56 | 0.0028 |
| j0 | 6 | 20 | 1.88e5 | 741 | 737 | 376 | 0.99 | 0.11 |
| j0 | 6 | 24 | 5.18e6 | 2882 | 4544 | 1915 | 1.58 | 0.028 |
| j0 | 6 | 28 | 9.94e7 | 20460 | 21960 | 8379 | 1.07 | 0.0070 |
| j1728 | 4 | 20 | 7.76e4 | 412 | 250 | 231 | 0.61 | 0.088 |
| j1728 | 4 | 24 | 3.39e6 | 2440 | 2465 | 1555 | 1.01 | 0.023 |
| j1728 | 4 | 28 | 5.47e7 | 6474 | 13120 | 6263 | 2.03 | 0.0076 |

The precompute fits `r^1.00` for every type and scales as `r/w`: at 28 bits
it is 1.11, 0.37 and 0.55 operations per unit of `r` for generic, `j = 0`
and `j = 1728` — every one `≈ 2.2·r/w`, so the `j = 0` curve's is 3.0
times cheaper than the generic one's and the `j = 1728` curve's 2.0 times,
the ratios of their automorphism orders. The automorphism group, not the
solver, buys that.

The descent is where width matters. On the secp256k1 shape at 28 bits, 64
targets, all recovered (`ic prime --curve secp256k1 --bits 28 --width W
--targets 64`):

| width | orbits (certified) | precompute | mean descent | charged | charged vs folded rho | whole process |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2256 (2105) | 8.48e7 | 21400 | 0.91 | 0.32 | 0.014 |
| 2 | 4511 (4230) | 6.85e7 | 10260 | 1.89 | 0.67 | 0.018 |
| 4 | 9022 (8478) | 4.98e7 | 4534 | 4.28 | 1.53 | 0.025 |
| 8 | 18044 (16970) | 4.70e7 | 1791 | 10.8 | 3.87 | 0.026 |
| 16 | 36087 (33935) | 4.63e7 | 1256 | 15.4 | 5.51 | 0.027 |

From width 4 the charged descent beats even the folded rho, and the precompute
gets *cheaper* as the base widens (fewer probes end in a full fruitless
sweep). P-256's shape runs the same way, reaching a charged 21× (12.8×
against folded rho) at width 16.

**What this is not.** The whole-process ratio stays near 0.01: the database
costs `≈ r/w` operations where rho costs `√r`, so a charged win survives
the whole accounting only when it is amortised over `Ω(√r)` targets — and
for many targets the fair opponent is not per-target rho but rho with
precomputation (Bernstein–Lange, `preprocessing_rho` / `ca_precomp`), whose
`≈ 2√(rT)` for `T` targets this pipeline does not approach. These are
2-summand decompositions, which is also why no prime-field rung here could
threaten a deployed curve: at 256 bits the precompute alone is `≈ 2^256/w`.

### Options

- `--curve NAME` (any prime profile of `ic list`) or `--type generic|j0|j1728`
  (`koblitz` is `j0`); neither means `--type generic`.
- `--bits` 8..=40 (default 24): the scaled field. The certificate and rho reach
  further; the precompute's `r/w` does not, and `--max-ops` (default `2^32`
  group operations) ends it as `incomplete`.
- `--targets` (default 32): known answers descended against one database. A
  descent's cost is heavy-tailed — its median is about half its mean — so a
  charged ratio from a handful of targets is noisy.
- `--width` (default 2), `--orbits`, `--relations-per-orbit` (default 1.5,
  which certifies about 93% of the orbits), `--no-rho`, `--seed`,
  `--known-log` / `--random-target`.
- `--solver semaev` runs the reference Semaev `S₃` solvers instead
  (`ec_index_calculus` for generic curves; `ec_index_calculus_j0`'s orbit or,
  with `--eisenstein`, Eisenstein-lattice base for `j = 0`) and the reference
  Floyd rho, in the general `num-bigint` arithmetic, compared in wall time. It
  is `O(p^{3/2})`, so `--bits` is held to 24, and it needs a prime-order curve,
  so `j1728` is refused. Its knobs are `--factor-base`, `--extra-relations`,
  `--max-trials` and `--attempts`.

## Random fixtures and custom parameters

    ./target/release/ca-ic generate --degree 11 --curve-a 1 --seed 42 --out fixture.json
    ./target/release/ca-ic inspect --file fixture.json --json

Generation randomizes the known scalar and target, not every field or
curve coefficient. The degree/coefficient select the curve; the existing
constructor chooses its field polynomial and subgroup generator.

A parameter document has schema_version 1 and these fields:

- name
- field
- a and b
- subgroup_order and cofactor
- optional generator and point coordinate pairs
- optional fixture containing known_log and seed

All integers except degree, polynomial_terms, schema_version, and seed
are strings, in decimal or hexadecimal with a 0x prefix. Unknown fields
are rejected. The input file limit is 1 MiB.

Field forms:

    {"kind":"prime","modulus":"97"}
    {"kind":"binary","degree":9,"polynomial_terms":[9,1,0]}
    {"kind":"binary_abstract","degree":131,"representation":"normal-basis metadata"}

Polynomial terms include the leading degree and constant term; they
must be unique. The inspector verifies irreducibility using polynomial
GCD and Frobenius identities. Abstract binary profiles accept only
Koblitz base-field coefficients a in {0,1}, b=1, and no coordinates.

See prime-example.json and binary-example.json for complete examples.

A factor-base recipe has schema_version 1, degree, curve_a, and a spec:

    {"schema_version":1,"degree":15,"curve_a":1,"spec":{"kind":"divisor","indices":[0,2]}}

Spec kinds are factor, divisor, frobenius_union, two_torsion_saturated, and
pruned (a parent spec plus the canonical abscissa of every retained signed
orbit). A recipe is rejected on any other curve.

## Meaning of validation

The inspector reports every check separately:

- strict numeric and canonical coordinate ranges;
- nonsingularity;
- exact irreducibility for a supplied binary polynomial;
- fixed-base Miller-Rabin screens for prime fields and subgroup orders;
- supplied points on the curve and annihilation by the declared order;
- supplied known-answer identities;
- exact Koblitz cardinality using an integer trace recurrence;
- the necessary Hasse bound for a declared cardinality.

Miller-Rabin passes are not primality proofs. An annihilation check does
not independently prove exact point order. Hasse's bound is necessary,
not a cardinality certificate. General prime/binary point counting,
missing points, and unsupported coordinate representations are reported
as not_checked. The aggregate checks_passed status means none of the
performed checks failed, not that all possible properties were proved.

Binary inspection supports degrees 2 through 768. Prime-field inspection
supports moduli at most 1024 bits. Curve names are descriptive; they do
not change these validation rules. The challenge corpus in
`challenges/ecc/` publishes parameters up to those limits.

## Deciding whether a cell is worth running at all

    ./target/release/ca-ic budget --degree 131
    ./target/release/ca-ic budget --degree 233 --summands 4
    ./target/release/ca-ic budget --standard --summands 4 --json
    ./target/release/ca-ic budget --degree 113 --no-frobenius

Every other cost figure this tool produces is measured after the fact: the
`vs_rho` block below times a run that already happened, and it is reachable
only from inside a workflow with `baseline.rho` set. `budget` answers the
question asked *before* spending anything — at this degree and arity, how many
operations may a single point decomposition take?

It charges relation collection **and** sparse linear algebra against the same
rho budget and inverts for what is left. With factor base `F_V` of dimension
`l`, `m` summands, and `R` the mean Frobenius orbit size on `V`:

- `|F| = 2^l`, and the linear-algebra dimension is `D = |F| / R`;
- a random target decomposes with probability `min(1, 2^(ml−n) / m!)`, so
  relation collection makes `D / p` attempts;
- sparse linear algebra costs `m · D²`, and holds `D` entries;
- rho is `√(πr/2) / √(2n)`, the same formula as `rho_expected_steps`, evaluated
  in logarithms so degrees past 63 stay representable.

Then `log2 budget = log2(rho − linear algebra) − log2(attempts)`. Linear algebra
does not depend on the solver, so a cell whose linear algebra alone exceeds rho
is lost before anything is attempted, and **a non-positive budget means the cell
loses to rho even with a decomposition oracle that is free** — reported as
`free_oracle_loses`, because no solver engineering can rescue it.

A second gate is charged separately. A decomposition must first *build* its
Weil-descended system. Every Frobenius power is `F_2`-linear, so a `K`-monomial
`x^e` costs Boolean degree equal to the Hamming weight of `e`, not `e`; the
descended degree is `m · min(m−1, l)` and the system has about
`Σ_{i ≤ D} C(ml, i)` monomials. When that count exceeds the whole budget —
`anf_blocks` — the obstruction is the **size of the system, not the difficulty
of solving it**, and the cell is blocked whatever solves it. A cell is `viable`
only when the budget is positive *and* the system fits inside it.

Options:

- `--degree N`: the extension degree. Not capped at 63 like the run commands,
  because nothing is constructed — only charged.
- `--standard`: charge the nine standardised binary degrees instead of one.
- `--summands M` (2–16): a single arity; omit to table every arity.
- `--dimension L`: charge this exact dimension rather than the best one.
- `--max-arity K` (default 6): largest arity tabled.
- `--no-frobenius`: withhold the orbit quotient, which isolates exactly what it
  buys. Crediting it may only widen what a cell is worth, never narrow which
  dimensions may be chosen: a subspace that is not Frobenius-stable is a
  perfectly legal factor base, it simply forfeits the quotient and is charged
  with `R = 1`.

Limits, refused loudly rather than silently worked around. A dimension at or
above the degree is rejected — a factor base spanning the whole field is not
one. Orbit reduction is computed for odd prime degrees only, where Frobenius
fixes exactly the subfield and every other orbit has length `n`; a composite
degree is charged with no quotient rather than with a wrong mean, because a
number that does not describe the run is worse than no number.

Status is `complete` whenever the arithmetic ran; it says nothing about whether
any cell was viable. The result is a verdict under a declared cost model, not
an attack and not a lower bound on ECDLP. Two charges are load-bearing and are
listed in the report's `limitations` so they can be argued with: sparse linear
algebra at `m · D²`, where a method with a materially lower exponent would
relax the gate on `l` and could revive arity 3; and one operation per ANF
monomial, which binds every method that *materialises* the system — Gröbner,
WDSat, CNF-SAT, crossbred, msolve — but not one that never materialises it.
Polylog factors are dropped on both sides, so the comparison is fair to within
them but not to within constants.

## Comparing factor bases

    ./target/release/ca-ic compare --degree 7 --curve-a 1 --samples 3 --holdout 2 --seed 42 --out comparison.json

Comparison uses the degree-ord_n(2) irreducible-factor family already
implemented by the materialized builder. It is not a search over every
possible factor base — `search` is. It launches one child process at a
time, each using only generated known-answer inputs. All candidates
receive the same training fixtures and solver settings.

A candidate must complete and verify every training run before it is
eligible. The training winner has the smallest observed median process
wall time; it must then verify separate generated holdout fixtures.
Failed and timed-out attempts remain in the report. If no candidate
passes, selected_factor_index is null and the result is inconclusive.

Comparison limits are 16 candidates, 1..8 training samples, 1..8 holdout
samples, and a per-child watchdog of 1..120 seconds (default 30).
Standalone run limits are algorithmic; the comparison watchdog applies
to child runs launched by compare.

Selection time includes process startup, curve and factor-base
construction, relation collection, matrix solving, verification, and
report emission. Child completion is polled every 10 ms; very small
timing differences should not be interpreted as meaningful. The report
also includes the total comparison time, so selection and unsuccessful
candidate costs remain visible. A selected candidate is a bounded
observation, not a global optimum, scaling claim, or challenge result.

## Reports and resource accounting

Add --json for machine-readable output or --out PATH to save the JSON
report while retaining the human progress display. Output files are
created exclusively: an existing path is never overwritten.

Run, comparison and search reports include normalized parameters,
known-answer fixtures, seeds, solver settings, status, counts, stages,
elapsed time, platform, package version, and a BLAKE3 fingerprint of the
executable. Run reports also carry the factor-base recipe and its size,
per-stage timing, and the relation accounting (independent, dependent and
inconsistent relations). Inspection reports retain normalized inputs and
the input-file hash. Generated parameter documents remain directly
importable.

On macOS and Linux, CPU time and peak resident memory are sampled with
getrusage before report emission. Peak RSS is normalized to bytes.
Each comparison or validation run is a fresh process; its resource
counters therefore do not inherit earlier candidates' high-water marks.
Parent counters cover the parent only. Unsupported measurements are null,
never zero. A watchdog-killed child has no complete resource report.

Exit status is zero for completed synthetic operations and inspections
whose performed checks pass. Invalid inputs, incomplete experiments,
inconclusive comparisons and searches, and output-file errors are
unsuccessful. Clap usage errors use its standard nonzero exit status.

## Verification

    cargo test --release --test ic_framework --test ic_progress --test ic_prime
    cargo test --release --lib koblitz_
    cargo test --release --lib -- prime_orbit_index_calculus ec_index_calculus_curves

The end-to-end pipeline is gated in CI as well: `ic-e2e-benchmark.yml` runs
the whole method plus the in-process ρ baseline on three frozen ledger rungs
and fails closed on an unverified logarithm, a drifted seeded counter, or a
regressed same-host end-to-end wall ratio. What it checks, what passing
does not claim, and how to re-freeze after a deliberate change are in
[`ci/README.md`](ci/README.md).

Tests cover named profiles, custom prime curves, generated-fixture
round trips, reproducibility, malformed and ambiguous parameters,
resource reporting, a degree-11 synthetic run under both accountings,
every solver with three summands, comparison eligibility, separate holdout
inputs, a search that succeeds where the legacy family yields nothing, the
binding of recipes to their curve, and exclusive artifact creation. The
library tests cross-check the pair table, the exact census, orbit pruning
and the incremental relation solver against exhaustive search and the
dense modular solver.

## The pair table, folded by the signed Frobenius group

The base is closed under `π` and negation, so its pair sums are too, and
the table needs one key per `⟨π, −1⟩`-orbit rather than one per pair. The
canonical key is `1 + min_k x^{2^k}` — the sign costs nothing, since
negation does not move the abscissa. Measured at `n = 61`: 122 times fewer
stored pairs, a base 11.0 times wider at 4 GiB (42302 → 467128), 122 times
fewer descent probes, and **197×** end to end per decomposed target at
matched bytes — 2.0× of which is the fold on the code as it stood, the
rest being five costs that only a base eleven times wider makes visible.

Recovery is `O(n)`, not `O(|F|)`: a folded entry names the signed orbit
one summand lies in, in the high half of its rest word, so recovering the
summands walks 122 points rather than 177632. It costs no memory — the
tag is spent out of the rest, not added to it.

The key itself is the least rotation of the abscissa's coordinates in a
normal basis, where the Frobenius *is* a rotation — `FrobeniusCanon` in
`koblitz_fast.rs`. Computed instead as a chain of `n − 1` squarings a
probe costs 1125 ns rather than 340 and the fold is worth 2.0× rather
than 2.8×.

The naming is done in a **normal basis**, where `π` is a one-bit
rotation of the coordinate word and the orbit is that word's `n`
rotations: the key is the least of them. In a polynomial basis the same
key is `1 + min_k x^{2^k}`, `n − 1` squarings, and that cost the fold
most of what it was worth — 733 ns against 85, and 2.0× end to end
against 3.3×.

- `koblitz_fast::NormalBasis` builds the basis and is the key; the two
  keys pick different representatives of the same orbit, so a folded
  table is not portable across the change.
- `PairSumTable::build_within` reaches for the fold as its last tier, when
  neither the full nor the compact table fits the budget. That is still
  right after the cheaper key: what the fold buys is a *wider* base, and
  the base is fixed by the time the tier is chosen.
- `PairSumTable::folded_byte_size` is the sizing law to choose a base by.
- `PairSumTable::contains_pair` is the probe on its own, without the
  `O(|F|)` summand recovery a hit would otherwise charge to it — one
  target at a time, which is *not* how the `m = 3` scan probes and costs
  roughly twice as much on a folded table; see the probe-shape bullet
  below before quoting it.
- `docs/ic/params/k0n61-subgroup-folded.json` asks for a 300000-point
  base, which only the folded tier can hold.
- `examples/koblitz_orbit_fold_width.rs` is the measurement;
  `docs/ic/runs/koblitz-orbit-fold-20260913.json` is what it produced.
- `examples/koblitz_fold_cost.rs` prices the canonicalisation on its own,
  four ways: the squaring chain serially and eight points in flight, a
  shift reduction for a sparse irreducible, and the normal-basis
  rotation.  At `n = 61` that is 846.8 / 733.7 / 1299.3 ns against
  **85.5**.
- `examples/koblitz_orbit_fold_width.rs` also prices a probe in the three
  shapes the code probes in, because they are far enough apart that "a
  probe" has to say which.  Median of three runs at `n = 61`: one target
  at a time the fold costs **2.8×**, blocked at the descent's own
  `BLOCK = 1024` and prefetched **2.0×**, and inside the `m = 3` scan
  itself **1.51×**.  What separates the columns of that last one is
  **74 ns** a base point, and the canonicalisation measured alone is
  **76** — so the fold's cost in the descent is the canon and nothing
  else.  Read it down the columns: blocking buys the folded table
  **1.83×** and the compact table, the control, **1.35×**, which is what
  says the cause is the key's length.
  `docs/ic/runs/koblitz-probe-shape-20260913.json` records it, and what
  it does not claim.

- `docs/ic/runs/koblitz-degree61-folded-20260913.json` — the pipeline run
  whole at 300608 points / 2464 orbits: 32 of 32 verified, **330.7×** over
  ρ charged, and an unplanned A/B of the orbit tag and row filter in the
  real pipeline (collection units 31× faster, solve 65× faster, resident
  memory halved, relation counts identical unit for unit). Amortised over
  32 targets the wider base is *worse* than the 36112-point one; the two
  cross at about 3600 targets.

- `docs/ic/runs/koblitz-width-curve-20260913.json` — four folded widths at
  degree 61, 32 targets each, all verified. The charged ratio rises
  monotonically with width (71 → 76 → 141 → 326); the amortised ratio is
  flat at ~6.2 from 45872 to 50752, then falls to 4.21 and 0.673.
  Optimising the charged number alone points at the widest base memory can
  hold, which is the worst of them.

**Two laws, two questions.** `r_max ∝ M²/(C + β·log M)²` says how large a
subgroup can be attacked at all — a charged-regime statement, precompute
assumed paid. The width curve says which width is cheapest for `T`
targets at fixed `r`, where precompute is most of the bill. Memory sets
the reach; the target count sets how much of that memory is worth using.

## Persistent fixed parameters through degree 131

`ic fixed --params docs/ic/params/ecc2k130-fixed.json --dir runs/ecc2k130-fixed --stage select`
validates the actual fixed parameters and persists the factor base.
[Fixed parameters](FIXED_PARAMETERS.md) documents bounded collection, resumable
pair tables, precomputed logarithms, direct target equations and the complete
small-curve example. This CPU Python workflow accepts full-width coordinates;
the existing Rust symbolic engine remains limited to degree 63.

### Learned solver and budget selector

The fixed workflow accepts `--solver learned --selector-model MODEL.json`.
The upstream [solver selection report](https://github.com/aburan28/crypto/blob/main/docs/ic/SOLVER_SELECTION.md) describes the matched natural-query
benchmark, cost-sensitive tree, exact fallback and audited initial result.
The initial portfolio selected a constant pair-table policy; no speedup is established.
