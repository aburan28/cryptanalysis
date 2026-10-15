# Local smoke (correctness only)

Run in a shared, contended container on 2026-10-14. These files hold no
timing value, and none may be quoted as one.

* `direct_arm_checks.json`: `arm.py` run directly on Q0 for every arm kind.
  Steps match A's receipts (10,203,425 at seed 202610061) and B's (12,804,216
  at seed 831000). IC took 8,845,441 probes for the cached, fresh-B and A
  producers. The fresh table's 600 logs equal B's archived table.
* `correctness.json`: `run_schedule.py --segments Q1,F1 --one-per-arm --cpu 1`
  then `verify_receipt.py --correctness-only`. All 10 arms ran on Q0 and all 5
  fresh-panel arms on point w00 (15 valid rows). Every identity check passes:
  one scalar per point, oracle replay, Q0 equal to the sidecar, identical
  steps (A's 14,229,982 and 13,159,092 at seeds 202610064/5; B's 9,447,525
  on w00 at seed 830000), identical probes (Q0 8,845,441; w00 14,455,639, as
  in B's Panel B), and fresh logs equal to B's archived table.
* `cargo-test-r819.txt` (12 tests) and `cargo-test-r770.txt` (32 tests):
  `cargo test --release --locked --bins`, all passing.

The smoke run used a `protocol.json` that differed from the committed one only
in the wording of `design.time_guard` (made adaptive afterwards), so its
recorded protocol digest differs.
