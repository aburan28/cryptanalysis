# Review and replay the S3 root Bloom experiment

The source-bound result is in [RESULT.md](RESULT.md). The two Rust programs
are the exact-table [reference](reference.rs) and the [Bloom candidate](candidate.rs).
The stored JSONL files are the original one-target runs; the manifests retain
their original source and executable hashes and absolute paths. They are
historical receipts, so an archive replay does not rewrite them.

## Checkout and build

The experiment's Cargo manifest uses the sibling `crypto` repository through
`../../../crypto`. Check out both repositories beside one another:

```text
parent/
  cryptanalysis/
  crypto/
```

The tracked `crypto` sources used for the frozen run match published revision
`8ab924b935923df9faac25915ed7d9849974de0b`. Check out that revision in
the sibling repository for a source-matched rebuild. The experiment's own
`Cargo.lock` controls dependency resolution. The manifest also records the
hash of a locally generated sibling `crypto/Cargo.lock`; that file is not
tracked in the sibling repository and is not used by this crate's Cargo build.

From `cryptanalysis/experiments/koblitz-s3-root-bloom-20261009`, run
`cargo test --release --offline` after the sibling dependency is available.
The component hashes in `bloom_manifest.json` identify the exact `crypto`
source files and Cargo inputs used for the recorded runs. A new build checks
the code on that machine; it does not recreate the archived executable hash.

## Check the archived result

Run `python3 validate.py --archive` from this directory. This checks the
candidate and reference source hashes against their manifests, all ten raw
one-target rows, semantic equality, timing phase sums, diagnostic counters,
memory receipts, and the recorded Sage result. It deliberately skips
comparison against the original executable files, which were not committed.
The stricter `python3 validate.py` remains available in the original frozen
workspace with those executable files present.

The public factor-base points and orbit labels needed for an independent
mathematical replay are included in `replay_base.json` (SHA-256
`b4a1ea4a68d305bc7dd86e2dca56cb2d078f48ef9721d0f1ea28526419d99dca`).
On this machine, use the repository's checked Sage launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python /absolute/path/to/cryptanalysis/experiments/koblitz-s3-root-bloom-20261009/replay_sage.py --archive
```

The archive replay independently verifies the target equation, all 238
recorded four-point relations, relation-matrix rank, and scalar point replay,
then compares its result with `independent_sage_replay.json`. It uses the
included factor-base file and does not require the original binaries.

The original `freeze.py` and `run_panel.py` intentionally reject overwriting
their frozen outputs. A new timing study needs a new workload, manifests,
output directory, and host-isolation receipt under the repository's IC
measurement rules.
