# Execution record

Working tree starts from crypto 275beb93f3bf33ade6c19f19e8b336027a00b297
and cryptanalysis 033bdcbe10e768e2a43130169f094d6d197d5148.
The implementation revision and hashes are recorded separately beside this
file. Protocol: `../../PROTOCOL.md`.

Native Rust environment, for each command:

```sh
export RUSTUP_HOME=/workspace/tools/rustup
export CARGO_HOME=/workspace/tools/cargo
export PATH=/workspace/tools/cargo/bin:"$PATH"
```

From crypto root:

```sh
cargo test --release --offline --locked --manifest-path tools/binary-genus2-cover/Cargo.toml
tools/binary-genus2-cover/target/release/binary_genus2_check --a both \
  --output research/binary_genus2_cover_20261014/runs/run-20261014T1442Z/n83.json
tools/binary-genus2-cover/target/release/genus2_identity \
  research/binary_genus2_cover_20261014/runs/run-20261014T1442Z/identities
tools/binary-genus2-cover/check.sh
cargo test --release --lib --locked --offline
```

The cover tests and package check pass. The first full-library compile failed
because the tracked ecbench records fixture was sparse; materializing its
exact path unblocked that compile. Full-library final status is recorded in
the final validation receipt. No unrelated library source was modified.
The permitted network grant on this test command allows its localhost
collaboration tests; it is not a cloud job or external experiment.

The package script runs formatting, tests, scoped Clippy, both n83 cases,
supplied-Q-without-scalar mode, IDC1 exact replay, and six CLI negative
controls. Its known-answer and supplied-Q JSON use fresh temporary paths.
Its full stdout/stderr is retained as `package-check.log`.

The final prime-provenance correction and final replay are recorded in
`PRIME-PROVENANCE.md` and `package-check-final.log`. The final command writes
`n83-final.json` and the initial `n83.json` remains unchanged. The final
source checks a=1 primality afresh and retains the historical a=0 receipt.

```sh
cargo run --release --offline --locked \
  --manifest-path tools/binary-genus2-cover/Cargo.toml --bin binary_genus2_check -- \
  --a both --output research/binary_genus2_cover_20261014/runs/run-20261014T1442Z/n83-final.json
```

The mirrored final command has the same flags, with its output named
`cryptanalysis-n83-final.json`. `cmp` verifies those final JSON files are
byte-identical. This is cross-checkout replay on one host, not independent-host
or independently authored Jacobian-arithmetic evidence.

The whole-library run completes with 4087 passed, 2 failed, 117 ignored.
The failed existing JV F4 tests are diagnosed with the same built binary:

```sh
target/release/deps/crypto_lib-dc60caf0642b04d8 \
  cryptanalysis::jv_cover::tests::replayed_f4_agrees_with_the_full_solver_and_the_oracle \
  --exact --nocapture
target/release/deps/crypto_lib-dc60caf0642b04d8 \
  f4_agrees_with_the_full_solver_and_the_oracle --test-threads=1 --nocapture
```

The isolated replay and serial pair pass; raw diagnostics are retained.
They do not replace or turn the failed full-library run into a pass.

From cryptanalysis root, the same native tests/package script use its own
suite backend. To reuse compiler dependencies locally only:

```sh
export CARGO_TARGET_DIR=/workspace/repos/crypto/tools/binary-genus2-cover/target
cargo test --release --offline --locked --manifest-path tools/binary-genus2-cover/Cargo.toml
tools/binary-genus2-cover/check.sh
```

CI uses a default target directory and the checked manifest/lockfile for each
repository. Missing tracked C-binding sources, CUDA headers embedded by the
library, challenge metadata, and calibration metadata were materialized in
the sparse mirror; the failed build logs are retained. No GPU execution is
involved. The suite backend is not asserted to be byte-identical to crypto's.

Formal proof (Lean 4.24.0; no external dependencies):

```sh
cd research/binary_genus2_cover_20261014/lean
/workspace/tools/lean-4.24.0-linux/bin/lake build
/workspace/tools/lean-4.24.0-linux/bin/lean BinaryGenusTwo.lean
```

The successful build and axiom audit are retained. `lean4checker` is not
installed. The initial failed auxiliary tuple proof is described separately;
no failed declaration is cited as checked.

Layout only, from crypto root:

```sh
python3 research/binary_genus2_cover_20261014/render_report.py
pdftoppm -scale-to 1250 -png research/binary_genus2_cover_20261014/report.pdf /tmp/genus2-pdf-review/page
```

All four rendered pages were inspected: equations, diagram identities,
count plot, tables and command lines are readable, without clipping. The
renderer only plots recorded values and typesets; all research computation
and identity verification use Rust. No Python curve arithmetic is involved.
