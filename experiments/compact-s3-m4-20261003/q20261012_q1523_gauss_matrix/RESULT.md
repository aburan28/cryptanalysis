# Q1523: Gaussian matrix parameter panel for exact S3 handoff

Raising CryptoMiniSat's column limit admits the previously discarded 265-by-3127 XOR matrix on the N53 exact two-leaf S3 handoff. The default 20% usefulness threshold then disables Gaussian elimination after reporting 18.0987% usefulness over 547 calls. Lowering that threshold to 10% retains the matrix but yields 611,588 conflicts at the 45-second CPU cap, compared with 2,000,002 conflicts in 41.74 child user CPU seconds under the default. All three exact unpinned runs remain capped or indeterminate. The large-matrix setting is therefore not selected for the next N83 handoff panel.

## Method and measured result

The fixed input is Q1519's known-positive N53 complement, ONB x-coordinate `8953252913413885`, on curve `EC1N53Ckb1hf77aab617904`. Its unpinned XCNF hash is `7644b17ed9524770d4f03a79b025342eda5e6c63137b6c987563b9d542f2cc7b`; the exact factor base has `B=24062` subgroup-usable points and 227 folded columns. The first pair is fixed outside this formula, leaving a two-leaf S3 handoff. The Q1519 pinned variant has a verified SAT assignment and independent group replay, establishing a positive control for this complement. Q1523 changes only solver parameters on the unpinned formula. Candidate ID and full pipeline work remain `null` because this is a PDP stage measurement.

| Solver setting | Matrix observation | Status | Child user CPU s | Exploratory wall s | Final reported conflicts |
| --- | --- | --- | ---: | ---: | ---: |
| Default (`maxmatrixcols=1000`, cutoff 0.2) | 265-by-3127 matrix rejected | `INDETERMINATE` at conflict cap | 41.74 | 90.49 | 2,000,002 |
| `maxmatrixcols=4096` | Admitted, then auto-disabled at 18.0987% usefulness | `WALL_CAP` | 38.08 | 120.05 | unavailable: stdout ended before final statistics |
| `maxmatrixcols=4096`, `gaussusefulcutoff=0.1` | Admitted; no disable message in saved log | `INDETERMINATE` at CPU cap | 45.01 | 65.46 | 611,588 |

All cells used CryptoMiniSat 5.14.7 binary SHA-256 `a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`, conflict cap 2,000,000, solver time cap 45 seconds, wall cap 120 seconds, and one process. The host lacks an isolation receipt, so CPU and wall comparisons are exploratory. The conflict counts measure search throughput at their recorded caps, not success probability or a solved-instance work exponent. Raw logs and receipts are in `runs/`; `validate.py` checks the input, source and binary digests, command, status, and raw-log hashes. A SAT output would also receive Boolean, S3 and independent curve-group replay.

The prior Q1519 N83 selected input has a 333-by-10707 XOR component rejected by the same default column limit. Q1523 did not rerun N83 with the widened limit because N53 did not pass the stated promotion rule. The conditional N131 independent-first-pair relation-supply model remains `2^123.289` batch multiplication calls, 62.289 bits above an abstract `2^61` reference in that same unit. This parameter panel supplies no update to the fully charged N131 exponent, which remains unset.

## Next experiment

Improve the target-conditioned second-pair lookup or branch ordering with a frozen N53 positive and N83 ordinary/holdout complement panel. Promote a solver change only after a verified unpinned positive solve or a stage cost improvement at a matched substantive work boundary, then measure natural-input yield and charge the result to the full one-target pipeline. Keep the same curve/factor-base records and candidate naming contract.
