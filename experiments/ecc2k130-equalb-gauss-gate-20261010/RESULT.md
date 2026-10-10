# Larger Gaussian components activate, with a 3.6–3.9× RSS cost

Raising CryptoMiniSat's native-XOR Gaussian limits admitted 8,262-by-13,084
matrices in both exact six-summand ordinary-query formulas. The default
setting admitted matrices no larger than 696-by-760. The larger components
were used during search, but all four R2 cells ended `BOUNDED_UNKNOWN` under
the frozen caps. The paired peak-RSS ratios were 3.932 for normal4 and 3.605
for W24. This identifies a solver-memory tradeoff; it does not select a
relation-producing PDP configuration.

## Inputs and accounting

The parent commit is `abbabdafbf746a92fe711e95871c6d2ff0587bcc`.
Both inputs are source-curve `EC1N131Ckb1h136f03e58c98` public query zero,
the same four independently checked raw target lifts, six summands, and
`B=11,743,888` distinct usable factor-base points before orbit folding.
The normal4 four-threshold counter XCNF has 443,029 variables, 418,074
ordinary clauses, and 300,963 native XORs; its raw SHA-256 is
`21b4c7c292fd1441f127428927fb6cf6c51849e279d97e72adbbd95343048d79`.
The W24 balanced-S3 XCNF has 336,209 variables, 340,190 ordinary clauses,
and 221,402 native XORs; its raw SHA-256 is
`f71601554772d6805b364638bc25fce1a23c96b0df65f4b9fd8a2dedd5f45e3a`.
The archived compressed/raw hashes and formula receipts are independently
replayed by `audit_gate.py`.

One pinned CryptoMiniSat 5.14.7 binary
(`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`)
ran with one thread, an internal 60-second limit, a 70-second external wall
guard, and a 4 GiB observed-RSS guard. `CONFIG.json` fixes the flags and run
order. Solver wall starts after formula decompression and hash verification;
those input costs remain in each receipt. The host had no isolation receipt,
so the timing and RSS contrasts are exploratory stage measurements. No
target-dependent IC pipeline was started; `candidate_id` remains `null`.

R1 preserved four `PRODUCER_FAILURE` receipts: sandboxed `ps` could not read
child RSS, and the fail-closed guard stopped each launch before search.
`RETRY.md` preregistered the same configuration as R2 under a local launch
where the RSS probe succeeded.

| R2 formula | Setting | Status / terminal | Wall s | Peak RSS MiB | Largest admitted matrix | Live restart rows |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| normal4 counter | 2,000 rows / 1,000 cols | `BOUNDED_UNKNOWN` / wall guard | 70.189 | 324.5 | 696 × 760 | 656 |
| normal4 counter | 9,000 rows / 14,000 cols | `BOUNDED_UNKNOWN` / solver indeterminate | 64.471 | 1,275.9 | 8,262 × 13,084 | 307 |
| W24 balanced | 2,000 rows / 1,000 cols | `BOUNDED_UNKNOWN` / wall guard | 70.254 | 340.3 | 696 × 760 | 743 |
| W24 balanced | 9,000 rows / 14,000 cols | `BOUNDED_UNKNOWN` / solver indeterminate | 66.999 | 1,226.9 | 8,262 × 13,084 | 306 |

All four R2 searches recovered five Gaussian matrices per initialization.
The large-limit runs subsequently admitted 8,131-by-12,822 matrices on
normal4 and 8,112-by-12,780 on W24. Their solver summaries show positive
elimination activity: the most active printed component recorded `108K`
calls for normal4 and `100K` for W24. Thus the result is more specific than
merely accepting larger matrices at initialization. The large-limit cells
reported 87,233 and 87,071 conflicts at their terminal solver limits;
default cells were killed by the external guard, so their final conflict
totals are unavailable. Restart rows are preserved as search diagnostics,
not evidence of a solved relation or a wall-time speedup.

## Decision and next gate

The 9,000-row/14,000-column, five-matrix setting stays diagnostic: it
activates the desired XOR components within 4 GiB, but its roughly fourfold
RSS demand did not resolve the frozen ordinary query. The solver summaries
show one matrix receiving most elimination calls while the other selected
matrices contribute much less. The next controlled gate should retain the
same two formulas and one public query, lower `maxnummatrices` from five to
two with the same large row/column limits, and compare component activity,
RSS, conflicts, and terminal status against these R2 receipts. If that
reduces memory without losing active elimination, test a preregistered panel
of ordinary queries and replay each candidate decomposition on the curve;
only verified relations and novel matrix rank can promote it to collection.

Reproduce the audit with
`python3 -B experiments/ecc2k130-equalb-gauss-gate-20261010/audit_gate.py`.
It rehashes both compressed and decompressed inputs and every raw transcript,
checks exact solver flags and matrix dimensions, and verifies all eight
recorded run statuses. The checked output is `AUDIT.json` with `status: PASS`.
