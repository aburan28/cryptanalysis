# Local smoke receipt (correctness only; no timing values)

Cloud-agent VM, 2026-10-15, rustc 1.97.0, run before the Tier 1 push:

`run_schedule.py --segments Q1,F1,H1` ran 17 rows through the real binaries,
wrapper, gates and verifier: Q0 (`qP`, `qH`, `qBaa`, `rT`, `qB`), w00 and w01
(all five arms each), and held-out slice 0..63 (`hP`, `hB`, 64 targets each).
`verify_receipt.py --correctness-only` wrote `correctness.json`.

- All 17 rows were valid. Every gate held:
  - the left-major arms reproduced B's archived probes and relations (Q0
    8,845,441; w00 14,455,639; w01 1,435,930);
  - the planted arms hit the predicted counts exactly (4,422,869; 7,227,999;
    718,146) with B's relations;
  - IC (both orders) and the tuned rho recovered one scalar per point, and
    each replays in the oracle;
  - Q0's scalar equals the sidecar;
  - all 64 held-out seeds recovered the same scalar in both orders, and all
    64 replay.
- The VM's clocks are not evidence. `correctness.json` holds probe counts
  (exact counts), not times.
- A dry run of the full analysis and of `make_figures.py` on this partial
  receipt completed; its outputs were discarded.
