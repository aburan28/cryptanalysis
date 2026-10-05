# Cost follow-up and IC boundary autolab, 2026-09-24

The continuation established **no new IC-versus-rho crossover and no
ECC2K-130 speedup**. The shifted-base geometry result remains valid, but its
first bounded algebraic-solver smoke produced no usable relations.

## Chained-S3 solver smoke

`solver_cost.py` adds a separate instrument restricted to the existing
degree-13, dimension-three, four-summand fixtures. It uses polynomial-basis
field circuits, native XOR constraints and CryptoMiniSat 5.14.7, with one
thread and a fresh solver for each query. The same-base arm orders leaf
coordinates to remove permutation duplicates; the shifted arm preserves
its distinct slot domains. Every allowed leaf abscissa is independently
lifted and filtered for prime-subgroup membership during fixture creation.

The declared [protocol](solver-protocol.json) preceded the smoke. Its inputs
are ordinary uniform nonzero scalar multiples of the fixture generator;
they are not planted decompositions. The smoke uses base seed 87006 and
stream seed 91001, with the same first 32 inputs in both arms.

| Arm | Queries | Native budget per solve | Verified relations | Rank gained | Cold time | Inputs covered by the offline exact oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Same base | 32 | 50 ms | 0 | 0 | 1.919 s | 1 |
| Shifted bases | 32 | 50 ms | 0 | 0 | 1.848 s | 12 |

Every query returned timeout. The elapsed times include fixture and template
construction, fresh solver loading, input generation and failed attempts.
There is no finite cost-per-useful-row estimate because the denominator is
zero. The slightly shorter shifted-arm time is not evidence of a speedup.
The larger proposed panel was not launched after this zero-yield smoke.

The native limit is not a hard operating-system deadline: solver loading,
verification and scheduling can extend elapsed time past 50 ms. The smoke
is a censored observation at this budget, not an UNSAT result or a rejection
of the mathematical construction. Full-width execution is unavailable in
this instrument.

The mathematical model has 38 Boolean unknowns before circuit gates, and
39 chained S3 field-coordinate equations. Their maximum Boolean degree is
three before Tseitin encoding. Additional leaf-domain and order clauses are
included. FFD/degree of regularity is unmeasured: this smoke has no Macaulay
degree instrumentation and makes no algebraic-frontier claim.

Affine S3 chains may omit witnesses containing an identity intermediate.
Returned leaf assignments are therefore lifted with all finite sign choices
and checked by actual group addition; rejected assignments are blocked.
An absent chain model would not establish absence from the full sumset.
The exhaustive oracle runs only after the charged collector stops and is
never supplied to query generation or the solver.

Correctness checks include independent field multiplication and squaring,
independent subgroup-filtered base reconstruction, independent S3 point-sum
identities, and complete circuits accepting fully assigned independently
constructed witnesses in both arms. These controls validate encoding paths;
they do not establish unrestricted solver completion.

Raw evidence: [solver-smoke.json](solver-smoke.json).

## Autolab measurements

The user-invoked `ic-boundary-autolab` skill was applied to the current ledger
in `/Volumes/SSD990/crypto`. Preflight passed. The ledger is more advanced
than the skill's older priority summary: it already records a finite n=53
amortized batch result, while its present first priority remains extraction
without explicit pair tables. The following are fresh single-fixture
measurements of the registered baseline arms, not shifted-base benchmarks.

| Beat | Timing class | IC | Rho | IC / rho |
| --- | --- | ---: | ---: | ---: |
| n=13 smoke | Whole process wall | 248.875 ms | 220.171 ms | 1.130× |
| n=37 | Whole process wall | 760.755 ms | 277.829 ms | 2.738× |
| n=41 | Algorithmic charged | 13,105.450 ms | 165.887 ms | 79.002× |

Ratios greater than one mean IC was slower. These are single observations,
not confidence-qualified timing estimates. Timing classes must not be mixed
when comparing rows. At n=41, 11,979.197 ms of the charged direct cost was
setup, about 91.4%; the current explicit support construction dominates.

The complete retained run receipts are included under
[autolab-followup-20260924/runs](autolab-followup-20260924/runs/). They were
copied byte for byte from
`crypto/research/sat_factor_base_review_20260908/autolab/runs/`:

- `20260924T134614Z-a3273b50fe`
- `20260924T134818Z-bf26cc6dc7`
- `20260924T134944Z-b501639a4a`

Absolute paths in those receipts identify the original measurement workspace;
they are historical provenance, not portable executable paths. The separate
Rust producer repository, its dirty source tree, and its executables are not
included here. These bundles make the recorded measurements inspectable;
rerunning the Rust producers still requires the recorded external environment.

Both producers exited zero in all three runs. Every state, claim draft,
claim check and producer log was inspected. All schema checks passed and all
48 review-manifest file entries verified. IC reached full coefficient rank
and its producer's group checks passed; each rho producer's verification
also passed.

The official states remain `PENDING_INDEPENDENT_VALIDATION`. The runner's
`independent_replay_pointer` currently points at its own draft; it is not
evidence of a separate replay. Manifest verification is also not independent
mathematical replay. No ledger row was promoted.

## Current degree-53 pair-support component

The existing relative-Frobenius support producer was also run on the retained
public synthetic n=53 base, using its statistics-only mode. It performs no
target join, relation extraction or logarithm extraction in this mode.
The current code recorded:

- 23,320 factor-base points and 220 orbit columns.
- 1,282,710 relative pair states and 2,565,420 stored root entries.
- Exactly 53× fewer stored root entries than its expanded comparison.
- 51,308,400 bytes of canonical packed payload as a lower bound, not RSS.
- 500.243 ms base ingestion and 830.639 ms support construction on 14 threads.
- Zero discrepancies in 4,096 deterministic equivariance checks.

An n=7 control exhaustively checked all 49 ordered endpoint pairs with zero
equivariance discrepancies. The executable and four selected source hashes
were recorded before execution and checked unchanged afterward. The
untracked `koblitz_fast_arith.rs` helper was not separately included in that
at-run source list; the executable hash is the authoritative implementation
pin. This is not a complete source snapshot or independent full n=53 replay.

The new support digest differs from the historical receipt for an understood
reason: the current root kernel handles equal nonzero endpoints as a linear
equation and returns the single root twice. The 220 diagonal states formerly
classified as exceptional are now included, increasing stored entries by
440 and unique root codes by 220. The producer's `regular_*` field names
therefore include these single-root states. Entry counts must not be read
as counts of distinct roots.

The existing root tests passed against the slow general-field reference on
generic pairs, direct Semaev evaluation on degenerate pairs, and exhaustive
tiny-field root existence. The faster historical-to-current construction
time is not promoted as a speedup: the contracts differ and there was no
matched repeated baseline timing. These arithmetic changes already existed
in the user's working tree; this task did not implement them.

Receipts and comparison metadata are in
[autolab-followup-20260924](autolab-followup-20260924/); the compact combined
record is [summary.json](autolab-followup-20260924/summary.json).

## Validation and decision

- All 13 Python tests pass under the installed Python 3.14 runtime.
- All four targeted Rust S3-root tests pass.
- The original geometry source hashes and the solver-smoke source hashes
  still match their recorded receipts.
- All three autolab artifact manifests pass without mismatch.

The next useful experiment must demonstrate actual relation extraction with
complete accounting. Simply enlarging these SAT timeout budgets or citing
the 53× support compression would not establish that. The evidence favors
investigating constraints that propagate pair compatibility earlier, while
charging any support preprocessing and retaining ordinary unsatisfied inputs.

To reproduce the bounded smoke with the installed binding:

```sh
/opt/homebrew/bin/python3.14 experiments/shifted-base-geometry/solver_cost.py \
  --smoke --out /tmp/shifted-base-solver-smoke.json
/opt/homebrew/bin/python3.14 -m unittest discover \
  -s experiments/shifted-base-geometry -p 'test_*.py' -v
```

The output file must be new. The full panel remains an unexecuted experiment,
not a completed cost comparison.
