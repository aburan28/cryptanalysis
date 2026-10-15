# Local smoke (2026-10-15, cloud agent VM): correctness only

These are not timing evidence. The VM is a shared 4-vCPU guest. The runs' stdout files, which carry clocks, are not committed. Only the verifier's `--correctness-only` output is kept here, and it holds no timing values.

The smoke ran in two parts. A container restart killed the first one after the exactness rows.

- **`correctness_X.json`.** `run_schedule.py --segments X,S1,Q1,F1 --max-runs-per-segment 6`, interrupted after 5 rows: `sV`, then `qV` on Q0, w00, w01 and w02. All 5 rows were valid.
  - Stage exactness covered 12,000,064 words with 0 variant-B and 0 lift_scan disagreements, and the pair certificate equalled the frozen one.
  - Online exactness covered every probe word: 8,845,441 on Q0, 14,455,639 on w00, 1,435,930 on w01 and 2,488,916 on w02, 27,225,926 in all, with 0 disagreements.
  - The scalars replayed in the oracle, and Q0's equalled the sidecar.
- **`correctness_S1_Q1.json`.** `run_schedule.py --segments S1,Q1 --one-per-arm`: 10 of 10 rows were valid.
  - Stage arms: `sA`, `sB`, `sBaa` and `sBx2`. Each reproduced the frozen pair certificate and its mode's frozen rotation counts.
  - Q0 arms: `qF`, `qL`, `qG`, `qFaa`, `qFx2` and `rT`. All IC arms had the same 8,845,441 probes and the same relation. IC and tuned rho agreed on scalar 3141592653589793, which equals the sidecar.
  - In this file the two exactness checks read `false` only because this subset contains no `X` rows.

Together the two parts ran every arm kind through the real binaries, wrapper, gates and verifier. A dry run of the full `verify_receipt.py` analysis and of `make_figures.py` used synthetic timings for all 178 scheduled rows. It ran end to end, and it correctly returned `invalid` because the synthetic rows fail exactness. Those outputs were deleted and are not committed.
