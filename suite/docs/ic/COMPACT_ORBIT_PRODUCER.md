# Compact Koblitz orbit producer on `main`

This page records the source promotion for `examples/koblitz_s5_sat_instance.rs`. The example is a bounded research producer for S5/four-factor relations on the implemented binary Koblitz rungs (`n = 7, 11, 13, 17, 19, 23, 37, 41, 53`). It is not an ECC2K-130 solver. Its purpose here is to make the compact Frobenius-orbit relation and rank experiments reproducible from `main` without depending on a long-lived feature branch.

The example is based on feature-branch merge `70bbbd618c5077a2a9c8d1afa16704c5a5c06bb8` (PR #714), whose Git blob ID was `3af182a7ddb8f18d17c8e45e587b64b0a25c76b3`. This promotion makes two equivalent Clippy cleanups in the example (one-hot matching and closure borrow release), yielding blob `5aaae25c553fa7f94428ddf539d4b61e9a3cf820`. The arithmetic module is based on that merge's blob `af761afbcba3e94620948c6f0bdc84aaeb9a4e2e`; this promotion makes an equivalent iterator-search change and removes an unconditional guard in a test for the pinned Clippy check, yielding blob `97f50c3519355d5b406b031f5993ab3c65a22865`. The main-branch integration adds the arithmetic module declaration and the SAT solver methods actually called by the producer: lazy theory clauses and deterministic saved-phase controls. It also preserves root UNSAT and XOR row counts when exporting extended DIMACS, which the producer's empty-edge-domain test requires.

The independent n=53 replay from PR #714 is retained under `research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924/`: `results.json`, `claim_relation_yield.json`, `independent_replay_20260924_codex/replay.py`, and its certified `base_header.jsonl.gz`. These are the script's exact local inputs. After the release build, run `python3 research/sat_factor_base_review_20260908/autolab_orbit_extract_20260924/independent_replay_20260924_codex/replay.py --variant deterministic --out /tmp/compact-orbit-replay` to recompute twelve archived public synthetic witnesses with independent Python field and group arithmetic. Choose a fresh output directory. The replay is positive relation evidence only.

The producer's CLI is:

```text
<n> <a> <eta_num> <eta_den> <planted|natural|proven_negative|scalar> <seed> <conflicts> <models> <internal|emit_xor|validate_model|stats|coverage|relative_pair_stats|batch_external_rank|batch_orbit_extract>
```

`KIC_ALGEBRA_ENCODING=orbit_factorized` selects the orbit encoding. `KIC_ORBIT_BATCH_ONLY=1` enables compact batch extraction in the internal backend; `KIC_ORBIT_TARGET_SCALARS` may supply a fixed scalar list. The producer also contains a separate `batch_external_rank` backend for `n <= 19`, which uses CryptoMiniSat and a locally specified `KIC_BATCH_ARTIFACT_DIR`. Consult the code for other experiment controls and retain the exact environment, factor-base input, seed, and output JSON with each run.

Validation for this source promotion uses:

```sh
cargo test --lib koblitz_fast_arith --offline
cargo test --lib lazy_clause --offline
cargo test --lib extended_dimacs_export --offline
cargo test --example koblitz_s5_sat_instance --offline
cargo build --release --example koblitz_s5_sat_instance --offline
```

These checks establish that the producer builds and its bounded arithmetic, SAT, export, and model-equivalence tests pass. They do not establish an end-to-end PDP or DLP gain, an unknown-target recovery, or a speedup over rho. The compact batch-only path omits SAT solving, so its relation output is a stage diagnostic; its timing and SAT-verification labels need the follow-up accounting correction before they can support cost comparisons. Exceptional cancellation inputs still need a separately validated path.
