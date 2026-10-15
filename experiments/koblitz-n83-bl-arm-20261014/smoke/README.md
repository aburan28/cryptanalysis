# Local validation receipts (2026-10-14; not timing evidence)

These receipts come from a shared, contended 4-CPU container. Every clock in
them is a diagnostic. The counts are exact.

* **`cargo-test.txt`**: `cargo test --release --locked --bins`, 27 passed,
  with local rustc 1.97.0. The workflow pins 1.99.0.
* **`control/`**: `control.py`, the positive controls, all four, at full
  N = 256. This is the dry run behind amendment A1 (see README.md). A second
  run gave byte-identical `rows.jsonl`. Tables are deleted after the checks.
* **`n83/ic_precompute/`**: `ic_precompute.py run` on CPU 0, a 22-minute rank
  stage.
  * It ran while other smoke work was on CPUs 1–3, so its P_IC (1,325.9 s)
    is not an estimate of anything.
  * Its factor-log table equals B's archived table in every field except
    `provenance.rank_stage_ms`.
  * The receipt's equality check was re-applied after that comparison was
    amended. The first version asked for byte identity, which the
    self-recorded rank time rules out. The rank stage was not rerun. See
    `smoke_note` in the receipt.
* **`n83/<impl>/bl/`**: `bl_table.py precompute --smoke --impl <impl>
  --budget-ms 60000`, a reduced 60 s budget instead of P_IC, then
  `bl_table.py check`. `table.bin` is not committed: 58–112 MB. Its SHA-256
  and BLAKE3 are in the receipts.
* **`n83/<impl>/panel/`**: `run_job.py --targets-limit 2`, Q0 block 0 and w00
  plus the step-identity run. The archived factor-log table was used.
* **`n83/<impl>/result*`**: `verify_receipt.py` on that reduced receipt.
  * With one fresh point, no interval exists and every reading is
    `no_result`.
  * The rB770 result lists `protocol unchanged since the run` because
    protocol.json was regenerated after that panel ran. The other two ran
    after the change.
