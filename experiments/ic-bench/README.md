# IC end-to-end benchmark

A reproducible benchmark of complete, verified index-calculus DLPs on toy
Koblitz curves `y^2 + xy = x^3 + 1` over `F_2^n`, following the naming and
accounting rules in `AGENTS.md`. Each run builds a factor base, collects relations
with the Macaulay (XL-closure) PDP solver until the achievable rank is reached,
solves the relation matrix mod `r`, descends every workload target, and checks
`[log Q]G = Q`.

```bash
python3 bench.py list                                        # suites and cells
python3 bench.py run --suite primary --jobs 1 --out-dir out/ # one unseen target per run, paired rho
python3 report.py out/primary.csv                             # verified online wall and rho/IC
python3 ../ic-candidate-catalog/analyze.py out/primary.jsonl  # contract validation
python3 bench.py run --suite ci --jobs 4 --out-dir out/       # secondary cold-operation regression
python3 compare.py baseline/ci.csv out/ci.csv                 # legacy regression gate
python3 -m pytest -q .
```

## What a row is

Each row is keyed by `(candidate_id, workload_id, run_id)`:

- **Candidate** `IC1N<n>Ckb1fb<B>PDP<m>xlRCsampleLAgaussTDpdpISO0h<12hex>`. It is the
  SHA-256 of the full manifest in `candidates/<id>.json`, which holds the field, curve,
  `isogeny: "none"`, the proved endomorphism record, the exact factor-base record, the PDP
  configuration and limits, relation collection, LA, target descent, and the SHA-256 of
  every executed source file. `B` is the actual usable point count, taken from
  `factor_base.FactorBase`. `xl` is the Macaulay/XL solver family. `PDP<m>xl` adds a solver
  code to the suggested vocabulary; `RCsample`, `LAgauss` and `TDpdp` are the AGENTS.md codes.
  Any change to the executed code gives new candidate IDs. That is intended: the
  manifest pins the implementation.
- **Workload** `workloads/<id>.json`. It fixes the curve, the query stream,
  the targets `Q_i = [s_i]G`, the rerandomization streams, the cache state and
  the rho reference and floor. The primary workload has one target; the factor base is the declared variable;
  every other input is paired.
- **Run** `<candidate>W<workload>R<k>`, where `k` is one more than the highest
  recorded run in `history.csv`.

`status` is `complete` only when every target's recovered log matches the
workload scalar and `[log Q]G = Q` holds. Otherwise it is `insufficient_relations`,
`budget` or `error`, and `total_operations` is empty (unknown).

## Primary one-target comparison

`primary` freezes three distinct public targets and runs each on the prefix,
geomtrace and random bases with one process at a time. It completes relation
collection and final matrix solving before starting the target clock. That
clock starts at the first target rerandomization and stops after scalar replay.
Target query creation, PDP work including failed attempts, relation checks,
descent, and replay have five exclusive wall-time entries that sum exactly to
`ic_online_ns`. Python loop overhead is charged to target descent.

The same public point is then solved by a measured three-set Pollard rho
control. The rho walk sees only the public point, uses a seed derived from
public curve and point coordinates, and verifies its recovered scalar. The
headline `online_speedup` is `rho_online_ns / ic_online_ns` only when both
answers verify. Target generation from a known scalar occurs before either
clock. Receipts preserve the exact target and both recovered scalars. The
three-target bootstrap interval in `report.py` describes variation across
those frozen points, not a claim about larger fields or ECC2K-130.

## Phase costs and the unit

`pdp-degree-heuristics/opcount.py` also meters the eleven exclusive phases of
supplementary `T_cold`. Every arithmetic entry point charges an exact counter: field
mul/inv/linear maps, point additions (`ec_mul` = bitlen + popcount additions),
lifts, Macaulay word operations, Boolean-system slicing, enumeration, and mod-`r`
Gaussian elimination. The counters are exact functions of the code and its inputs, so
CI compares them exactly.

`calibration.json` prices the counters in **rps** (reference picoseconds): each class
is weighted by its batch-throughput time on the calibration host, per field
degree, as integers. `calibration_id` is `ICBCAL1h` followed by 12 hex digits of the
SHA-256 over `{unit, weights}`. The weights are frozen, so totals are exact integers on
any host. Re-running `calibrate.py` gives a new ID, and runs under different IDs
are never paired. Caveats:

- The unit prices counted C/numpy work. Python bookkeeping is not counted. It appears
  as `priced_over_wall` (priced rps / wall ps), which is typically well
  below 1 at these sizes.
- `gf_inv` and `gf_lin` exist only as single ctypes calls. They are priced as that
  call minus a `Field.trace` call, which is noisy but small in every run.
- `rho_operations` = `round(sqrt(pi r / 2))` × the `ec_add` weight;
  `rho_floor_operations` = `round(sqrt(pi r / (4n)))` × the `ec_add` weight
  (rho on `{±tau^j P}` classes). `S_rps = total / sqrt(r)` and
  `S_ec_add = total / (w_ec_add sqrt(r))`. These boundaries are fixed by the
  workload record before any run.

**Instrument** work is recorded but not charged to supplementary cold operations.
It covers structure checks, exact-yield enumeration, and predictions. All
target PDP enumeration, including unsuccessful attempts, remains inside the
primary online interval.

### Oracle-assisted completion

For systems with `S >= 1` solutions, the Macaulay scan stops when the standard
monomials number `S`. `S` and the solutions are read from an exhaustive Moebius
enumeration. That enumeration is **charged** to the phase it serves (`pdp` or
`target_descent`) at `(N + 2) 2^(N-1)` `anf_op`, so no oracle work is free.
Refutations (`1` in the row space) need no enumeration. At these toy sizes the
enumeration is cheap, but it would dominate at cryptographic sizes. These totals
therefore measure this implementation, not an asymptotic XL cost.

## Suites

- `primary` has 9 one-target runs: three factor bases on each of three frozen
  `n = 13, m = 3, l = 3` public points. It is the default suite.
- `ci` is a secondary multi-target regression suite with 12 runs. At `n = 13, m = 3, l = 3` it runs {prefix, geomtrace, random} on 3
  workloads; at `n = 19, m = 2, l = 5` it runs {prefix, geomtrace, random} on 1
  workload. It finishes in well under a minute on four cores.
- `full` adds `n = 19` at `l = 5` and `l = 6` with more families, including
  `geomtraceu`, on 3 workloads each, plus `n = 23, l = 6`. It is not gated in CI.

## Recording and history

`bench.py run --record` does four things:

- It appends to `history.csv` and `results/receipts.jsonl`.
- It writes new manifests under `candidates/` and `workloads/`.
- It refuses to overwrite a manifest file with different content.
- It replaces `baseline/<suite>.csv/.jsonl`.

Record the baseline after an intentional change and commit it with that change.
`compare.py` pairs rows on `(bench_cell, workload_id)` and fails in these cases:

- A run is incomplete or unverified.
- A cell is missing, or its workload changed.
- The counters differ while the candidate ID is unchanged (nondeterminism).
- A cell's total, or the geometric mean of the totals, grew by more than
  `--tolerance`.

Wall time is reported and never gated.

## Other receipt writers (audit)

These writers keep their existing names and outputs. None mints an `IC1` ID.

- `ecc2k130/runner/codegen/indexcalc_e2e.py`, `indexcalc_fixed.py` and
  `autolab.py` have exact SHA-256 digests pinned in
  `docs/papers/ecc2k130-blackwell/evidence/source-manifest.json`, so they are
  not edited.
  - `indexcalc_e2e` counts logical calls in its own phase names, with no calibrated
    unit. It refuses degree-131 recovery.
  - `indexcalc_fixed` reports fixed-base stage checks.
  - `autolab` tunes rho kernels, so IC IDs do not apply to it.

  To enter an IC comparison, a run of `indexcalc_e2e` needs a candidate manifest
  and a mapping of its ledger onto the eleven phases. Until then it is a
  pre-convention artifact.
- `experiments/sage-ic-campaign/*` measures arithmetic stages, such as point maps, codecs
  and field operations, with its own intent and receipt files. Its ROADMAP already
  requires candidate IDs and complete phase charging before any IC claim. This
  harness is where such a claim would be measured.
- `pdp-degree-heuristics/monitor.py collect` meters every phase, but it writes the
  unnamed `pdp-collection-run/2` record. `bench.py` wraps it, names the run, and
  prices it.
