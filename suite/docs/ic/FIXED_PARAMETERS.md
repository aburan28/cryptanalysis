# Fixed-parameter index calculus

`ic fixed` runs a persistent CPU workflow on explicit K_0 parameters, including
the ECC2K-130 curve over GF(2^131). It uses the existing Python arbitrary-width
normal-basis arithmetic and Semaev engine. The Rust symbolic implementation's
degree-63 limit still applies to the older `run` and `workflow` commands.

The fixed workflow supports selection, resumable pair-table construction,
target-independent relation collection, factor-base logarithms, and target
relations. A target can finish once its logarithm is determined even when the
full factor-base database is incomplete. Every returned scalar is checked in
the group. Replaying an existing relation does not count as new rank.

## Run and resume

Build the CLI, then initialize the exact public ECC2K-130 profile:

```sh
cargo build --release --bin ca-ic
target/release/ca-ic fixed --params docs/ic/params/ecc2k130-fixed.json \
  --dir runs/ecc2k130-fixed --stage select --json
```

This validates the polynomial, its explicit image in the normal basis, the
generator, target subgroup membership, and the selected factor base. The profile
uses the public polynomial-basis coordinates and basis image already present in
the upstream [`ecc2k130/codegen/gen.py`](https://github.com/aburan28/crypto/blob/main/ecc2k130/codegen/gen.py) and [`ecc2k130/generated/eccF131.h`](https://github.com/aburan28/crypto/blob/main/ecc2k130/generated/eccF131.h).

Build a bounded number of new pair candidates and save the cursor:

```sh
target/release/ca-ic fixed --params docs/ic/params/ecc2k130-fixed.json \
  --dir runs/ecc2k130-fixed --stage pairs --pair-budget 10000 --json
```

Repeat to continue construction. `pair_budget` means the table is incomplete;
the CLI exits unsuccessfully and retains the committed work. Only a complete
pair table can certify that an exhaustive query has no decomposition. Table
construction uses SQLite on disk, so it does not allocate all pair entries in
RAM. This first implementation stores every admissible signed pair and all
collision buckets; it does not implement the Rust folded-table representation.

Use the small fixed profile to exercise the complete pipeline:

```sh
target/release/ca-ic fixed --params docs/ic/params/k0n9-fixed.json \
  --dir runs/k0n9-fixed --attempts 256 --pair-budget 10000 --json
# Same command: verify and reuse the completed results.
target/release/ca-ic fixed --params docs/ic/params/k0n9-fixed.json \
  --dir runs/k0n9-fixed --attempts 0 --pair-budget 0 --json
```

Other stages are `collect`, `logs`, `solve`, `status`, and `all` (default).
`collect` produces target-independent equations and certifies base logarithms
when rank is sufficient. `solve` reuses those logarithms or collects equations
containing the requested target directly. `all` attempts both stages. `--attempts`
is the maximum **additional** attempts per collection stream or target in the
current invocation. Attempts, including failures and timeouts, are retained.
Changing budgets does not invalidate the campaign.

For bounded Semaev SAT queries, use `--solver sat --pair-budget 0` and select an
interpreter with `--python /path/to/python`. It needs `python-sat` and
`pycryptosat`; the pair-table workflow uses the Python standard library only.
`--query-seconds` bounds pair searches cooperatively and supplies the native SAT
solve budget. The shared SAT engine additionally has a one-second process
watchdog covering encoding, solving and lifting; timeout is never reported as
unsatisfiability. SAT requires a Hamming-weight factor-base recipe. It uses Linux
`fork`. Run without Python `-O`, because the underlying arithmetic uses assertions.

The Semaev / Trimoska WDSat oracle for Frobenius-invariant subspace
bases lives on the Rust ladder (`ic run --solver wdsat --wdsat-binary
PATH`), not in this ONB / Hamming-weight fixed workflow. See
[`RESEARCH_WDSAT_IC_UNIFICATION.md`](https://github.com/aburan28/crypto/blob/main/research/notes/ecc2k130/RESEARCH_WDSAT_IC_UNIFICATION.md).
ECC2K-130's field is prime-degree (`n = 131`); the unified Semaev path
applies to that family on toys. Full-size `n = 131` remains bounded by
the free-oracle floor in
[`RESEARCH_ECC2K130_DECOMPOSITION.md`](https://github.com/aburan28/crypto/blob/main/RESEARCH_ECC2K130_DECOMPOSITION.md).

## What is stored

`campaign.sqlite3` is the durable record, with full SQLite transactions and
synchronous commits. It contains:

- Fixed mathematical parameters and the ordered factor base.
- The pair index, checksums and construction cursor, committed in chunks of at
  most 256 candidates. Interrupted chunks roll back together.
- Every completed probe's stream, counter and outcome. A relation witness and
  its probe commit in the same transaction.
- Verified sparse-support equations, factor-base logarithms and target results.
- Per-invocation phase timings, logical counters, reuse counts and source hashes.

The manifest identity includes the curve, basis, generator, factor-base recipe
and summand count. Target IDs are bound separately to their coordinates. Adding
a target can reuse the same precomputation; rebinding an existing ID or changing
the mathematical setup is rejected. Existing witnesses and scalar certificates
are checked before reuse. Completed target replay does not require a pair-table
rebuild or new decomposition queries.

One writer owns a campaign directory at a time. Use separate directories for
independent experiments. Distributed work allocation and cross-directory relation
merging are not implemented in this command. SQLite is the persistent store;
the expiring Redis artifact cache and GPU/RDMA reducers are not used by this CPU
workflow.

## Parameters and mathematical scope

The version-1 JSON format requires `curve`, `generator`, `factor_base`,
`summands`, and `targets`; `name` is optional. See the two checked-in profiles.
Coordinates and scalars accept decimal or hexadecimal strings without word-size
truncation. Unknown fields and duplicate JSON keys are rejected.

Supported curves have equation `y^2 + x*y = x^3 + 1`, odd degree between 3 and
131 admitting the existing type-II normal basis, and group order four times a
prime. Coordinates may be `type-ii-onb` or `polynomial`. Polynomial coordinates
require the polynomial and `onb_root`, the image of its generator in ONB
coordinates; the root equation and full-rank basis conversion are verified.

Factor bases are either `{"kind":"hamming-weight","weight":2}` or
`{"kind":"explicit-orbits","representatives":[{"x":"...","y":"..."}]}`.
Explicit representatives use the declared input basis, belong to the prime
subgroup, and must have disjoint signed Frobenius orbits. No logarithms are
supplied with the base. Materialized Hamming weights are limited to two above
degree 31 and four below; explicit bases accept at most 4096 orbit representatives.
Two or three summands are supported. All inverse-cancelling witnesses are excluded.

The supplied ECC2K-130 weight-two profile has **14 orbit columns and 3,668 signed
points**. Its three-summand coverage ceiling is about **1.21e-29** for uniform
nonzero subgroup targets. This is a functional fixed-parameter profile, with
an extremely low-yield base. The implementation reports this counting bound and
preserves incomplete runs. Practical completion at degree 131 has not been
established. A wider or differently structured base still needs measured yield
and affordable decomposition.

## Evidence and accounting

The [fixed campaign contract](https://github.com/aburan28/crypto/blob/main/research/fixed_parameters_20260915/contract.json)
compares identical complete workloads in ephemeral, durable and resumed modes,
with independent holdout seeds and three repetitions. The new pair query is also
checked against exhaustive group-sum enumeration on small curves. Degree-131
validation covers the actual parameters, basis conversion, bounded table progress
and incomplete SAT work. It does not infer full-size completion from toy runs.

Per-invocation counters include actual artifact loading, validation and arithmetic.
They are nested logical calls, not a common operation unit. Reports preserve
cumulative measured time; their phase accounting excludes final report archival,
output and connection close. The comparison separately measures the entire API
invocation, including archival and close. Cold work remains charged. Common
operations, S and rho/floor ratios stay null; no timing speedup or exponent is
claimed by this extension.

## Learned query policies

An opt-in `--solver learned --selector-model MODEL.json` policy selector uses
cheap pre-query features, exact witness verification and bounded pair fallback.
See [Learned solver selection](https://github.com/aburan28/crypto/blob/main/docs/ic/SOLVER_SELECTION.md) in the upstream research repository for collecting matched labels,
training a model, domain guards, and the initial no-routing-gain result.
