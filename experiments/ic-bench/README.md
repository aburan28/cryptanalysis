# IC end-to-end benchmark

A reproducible benchmark of complete, verified index-calculus DLPs on toy
Koblitz curves `y^2 + xy = x^3 + 1` over `F_2^n`, following the naming and
accounting rules in `AGENTS.md`. Each run builds a factor base, collects relations
with the Macaulay (XL-closure) PDP solver until the achievable rank is reached,
solves the relation matrix mod `r`, descends every workload target, and checks
`[log Q]G = Q`.

```bash
python3 bench.py list                                        # suites and cells
python3 bench.py run --suite ci --jobs 4 --out-dir out/      # out/ci.csv, out/ci.jsonl, manifests
python3 compare.py baseline/ci.csv out/ci.csv                # regression gate (tolerance 5%)
python3 report.py out/ci.csv                                 # paired factor-base table
python3 ../ic-candidate-catalog/analyze.py out/ci.jsonl      # contract validation and summary
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
  the targets `Q_i = [s_i]G`, the rerandomization streams, the cold target count, and
  the rho reference and floor. The factor base is the declared variable of a suite;
  every other input is paired.
- **Run** `<candidate>W<workload>R<k>`, where `k` is one more than the highest
  recorded run in `history.csv`.

`status` is `complete` only when every target's recovered log matches the
workload scalar and `[log Q]G = Q` holds. Otherwise it is `insufficient_relations`,
`budget` or `error`, and `total_operations` is empty (unknown).

## Phase costs and the unit

`pdp-degree-heuristics/opcount.py` meters the eleven exclusive phases of
`T_cold`. Every arithmetic entry point charges an exact counter: field
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

**Instrument** work is recorded but not charged. It covers structure checks,
exact-yield enumeration, predictions, and brute-force enumerations of systems
whose solution count the scan never reads. The receipt keeps it under `instrument`.

### Oracle-assisted completion

For systems with `S >= 1` solutions, the Macaulay scan stops when the standard
monomials number `S`. `S` and the solutions are read from an exhaustive Moebius
enumeration. That enumeration is **charged** to the phase it serves (`pdp` or
`target_descent`) at `(N + 2) 2^(N-1)` `anf_op`, so no oracle work is free.
Refutations (`1` in the row space) need no enumeration. At these toy sizes the
enumeration is cheap, but it would dominate at cryptographic sizes. These totals
therefore measure this implementation, not an asymptotic XL cost.

## Suites

- `ci` has 12 runs. At `n = 13, m = 3, l = 3` it runs {prefix, geomtrace, random} on 3
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

## Running a cell under ICMS

The [ICMS measurement standard](https://github.com/aburan28/crypto/blob/main/docs/ic/measurement/README.md)
in the crypto repository ([crypto#1177](https://github.com/aburan28/crypto/pull/1177))
can run one cell of this harness as a pinned, recorded measurement. Use it when
a wall time or a comparison has to hold beside another host or another
repository. The CI suite above stays the gate for counters.

ICMS adds three things a receipt does not have:

- **Isolation, recorded and graded.** The cell runs alone on a reserved core,
  with other threads moved off it by crypto's `tools/isolated_bench.py`, in a
  fresh interpreter with a built environment. Every 50 ms the runner samples
  the cell's run-queue delay and any foreign runnable task on the reserved
  core. It also reads hypervisor steal and PSI before and after the run. Each
  run earns a level from L0 to L3. Wall time is compared only when every run
  of both arms reached at least the level the spec declares.
- **The host.** It records the CPU model, microcode and flags, governor and
  turbo, SMT, the kernel command line, sysctls, virtualization, `cc --version`,
  numpy and Python. `calibration.json`'s `host` block records `node`,
  `machine`, `processor` (here `x86_64`, the architecture rather than a CPU
  model), `python`, `numpy` and `kernel_cflags`, but not the CPU model.
- **A spec and a comparison.** The cell is written as a YAML spec whose hash
  is in every record, a session can carry an A/A arm, and a comparison
  refuses any difference it was not told to expect.

**How it calls this harness.** crypto's `tools/icms/adapters/cryptanalysis_cell.py`
imports `bench.py` from a checkout beside crypto (`../cryptanalysis` by
default) and reads `calibration.json`. It then calls `bench.run_cell(cell,
calibration)` once in the pinned process. It refuses to run when
`bench.LIMITS` differs from the solver limits the spec pins. It never passes
`--record`, so nothing is written to `history.csv`, `results/`, `baseline/`,
`candidates/` or `workloads/`. Two git-ignored caches are still written on
first use: the C kernel under `../pdp-degree-heuristics/build/` and the
summation polynomials in `../pdp-scaling/sumpoly_cache.pkl`.
[`test_icms_interface.py`](test_icms_interface.py) pins every module name,
receipt field and counter that runner and its adapter read. Change them in
both repositories together.

A cell maps onto a spec as follows. crypto's
`docs/ic/measurement/specs/ca-k0n13-prefix-l3-m3.yaml` is a complete example.

| cell | spec field |
|---|---|
| `n` | `instance.curve.degree`, with `regime: koblitz` and `koblitz_a: 0` |
| `family` | `factor_base.params.basis_law`, with `family: binary_subspace` |
| `l` | `factor_base.params.dimension` |
| `seed` | `factor_base.params.basis_seed` |
| sign/Frobenius quotient rule | `factor_base.quotient`: `[negation]`, or `[negation, frobenius]` for the `invariant` law |
| `m` | `decomposition.arity`, with `method: algebraic` and `encoding: expanded_semaev` |
| `mode`, `LIMITS` | `decomposition.solver`: `name: macaulay-xl`, options `mode`, `formulation: direct`, `d_max`, `max_cols`, `max_rows` |
| `workload_seed`, `targets` | `instance.workload.seeds`, `instance.workload.targets` |
| `max_attempts` | `relations.max_trials`, with `collector: sample` and `stop: full_rank` |

The ICMS record keeps the receipt's figures under its own names:

- the rps total, as unit `cryptanalysis.rps` with the `calibration_id`;
- the `ec_add` counter summed over the eleven phases, as `count.group_additions`;
- `fb_points` as `usable_points` (B), and `geometric_points` as `signed_points`;
- `effective_columns` as `columns`;
- `ratio_to_rho` under `rho.plain`, and `ratio_to_floor` under
  `rho.signed_frobenius`. The spec names the one it compares against.

A receipt has no Boolean-system shape, so those PDP fields are null.

To run two cells as an A/B session with an A/A arm, check crypto out beside
this repository and install numpy and PyYAML:

```bash
cd "$(git rev-parse --show-toplevel)/../crypto"   # crypto checked out beside this repository
python3 tools/icms run docs/ic/measurement/specs/ca-k0n13-prefix-l3-m3.yaml \
                      docs/ic/measurement/specs/ca-k0n13-geomtrace-l3-m3.yaml \
                      docs/ic/measurement/specs/ca-k0n13-prefix-l3-m3.yaml \
                      --cpus auto --out /tmp/ic-bench-session
python3 tools/icms compare /tmp/ic-bench-session --a 0 --b 1 --declare factor_base.params.basis_law
python3 tools/icms audit-sessions /tmp/ic-bench-session
```

- `--cpus auto` reserves the highest-numbered whole core in the session's CPU
  affinity, never CPU 0's core and never every CPU the session may use.
- The session refuses to start on a busy machine. `--allow-busy` records the
  refusal and keeps every run below L2.
- Run it as root. A session that cannot move other users' threads off the
  reserved core earns L0. Its operation counts are still exact.

### Comparing these figures with crypto's or crypto-autoresearcher's

ICMS's audit (crypto `docs/ic/measurement/audit.json`) found these
differences between this harness's figures and those of the other two
repositories. An independent verifier re-checked each one.

- **Rho reference (X01).** `ratio_to_rho` divides by the analytic plain walk
  `sqrt(pi r / 2)`. crypto's `s_over_rho` divides by the cheaper of two
  measured walks on the same subgroup, setup included: signed-Frobenius
  (`A = 2n`) or negation (`A = 2`). In expectation the plain walk is
  `sqrt(2n)` more expensive than the `A = 2n` one, 6.78 at `n = 23`. In
  crypto's frozen `n = 23` and `n = 31` Koblitz runs the negation walk won,
  and the realized gap was 1.14 to 1.19.
- **Unit (X05).** `modr_mul` is priced at the speed of a CPython loop: at
  `n = 19` it costs 47.575 ns against 117.255 ns for `ec_add`, a ratio of
  0.406. crypto prices a relation-matrix row operation at 0.01135 of an
  addition at the same size, about 36 times lighter. rps and crypto's GAE are
  different units, and ICMS never compares them.
- **Stop event (X09).** A cell collects relations until the rank reaches the
  achievable rank (`m = 2`) or the effective column count (`m >= 3`), then
  descends every target. crypto's `ic bench` stops when the target's column
  is pinned. Relation counts and totals under the two stop rules are not
  comparable.
- **Targets (X10).** `ci` cells use `targets = 3`, and `ratio_to_rho` divides
  that three-target cold total by a one-target rho. The primary comparison in
  [AGENTS.md](../../AGENTS.md) uses one target. The ICMS specs for this
  harness use one target, and the adapter attaches no one-target reference
  ratio to a k-target total.
- **Uncharged work (X11).** Loading the summation polynomials and the
  `instrument` diagnostics are not charged. Compare only windows that leave
  out the same work.
- **Host and pinning (X16).** The calibration host's CPU model is not
  recorded, and `bench.py run --jobs` defaults to `os.cpu_count()` unpinned
  worker processes. Wall times from such runs do not carry across hosts.
- **Build (X17).** `kernel.py` compiles with `-march=native`, so the kernel
  that runs depends on the host, while the candidate ID covers only the
  `CFLAGS` string. ICMS records the compiler and the CPU flags in its capsule.

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
