# Replay the sparse S3 canonicalization experiment

The [result](RESULT.md) reports five paired, single-target runs. The
`reference.rs` program uses 53 rotations for normal-basis canonicalization;
`candidate.rs` uses the guarded longest-cyclic-zero-gap method. Both programs
perform the same exact S3 root-table lookup and witness verification.

## Source checkout and build

The Cargo manifest expects the `cryptanalysis` and `crypto` repositories as
siblings. The tracked `crypto` source files used for the frozen run match
revision `8ab924b935923df9faac25915ed7d9849974de0b`. Check out that
revision in `crypto` before a source-matched rebuild. The experiment's
`Cargo.lock` is tracked. The historical manifests also hash a locally
generated `crypto/Cargo.lock`; that file is not tracked in `crypto` and is
not an input to this experiment's Cargo build.

From this directory, run `cargo test --release --locked --offline` with the
required crates cached, or omit `--offline` when fetching them is necessary.
The candidate tests compare exact canonical keys and shifts for every binary
word through degree 13, deterministic N53 words, and roots from the N53 S3
index. A new build checks the published source on that machine; the binary
hashes in the frozen manifests identify the original executables.

## Validate the archived runs

Run `python3 validate.py --archive` from this directory. The archive mode
checks the local Rust source against the frozen hashes, candidate identities,
all ten raw outputs and ordered paired rows, exclusive online phase sums,
semantic equality, aggregate arithmetic, and the recorded Sage receipt. It
does not require the original executable files or write a new result. The
plain `python3 validate.py` mode checks the original binary paths in the
frozen workspace.

The factor-base points and orbit labels used by the mathematical replay are
included in `replay_base.json`, SHA-256
`b4a1ea4a68d305bc7dd86e2dca56cb2d078f48ef9721d0f1ea28526419d99dca`.
On this workspace, launch the replay through the repository's checked Sage
launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python /absolute/path/to/cryptanalysis/experiments/koblitz-s3-sparse-canonical-20261009/replay_sage.py --archive
```

The replay independently checks the target equation, all 238 four-point
relation witnesses, relation-matrix rank, and scalar point replay, then
compares the result with `independent_sage_replay.json`. Archive mode reads
only the files in this directory and leaves the historical receipt intact.

`freeze.py` and `run_panel.py` document the original frozen run procedure;
they reference original binary paths and an earlier local candidate manifest.
A new timing study needs its own frozen source and workload receipts. The
published five-pair panel remains an unisolated-host diagnostic; controlled
wall-time comparison requires the repository's isolated benchmark service.
