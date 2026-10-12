# Conjugate-x Bloom prefilter for the A1 three-summand scan

The scanner tests a raw x coordinate against a reusable Bloom filter before
computing its 53-element Frobenius orbit minimum. The filter contains every
x-conjugate of each exact pair-index key. A negative result skips the orbit
calculation; a positive result still uses the canonical key and exact pair
table, followed by the original point and scalar checks. The filter has
366,855 aligned 512-bit blocks, five positions per x, and a 23,478,720-byte
serialized representation. It loads directly into 64-byte-aligned blocks
with an incremental SHA-256 check.

The source is a portable extraction of the direct-aligned A1 scanner from
the October 9 archive. Its scan, filter, witness verification, and timing
paths retain the archived implementation. This package changes the binary
name and adds an independent regression fixture. The archived scanner source
has SHA-256
`2802db73622e8ead53a7365783d15407bed87f9e7d288edfa4e70d33b43c3e56`.
The earlier unaligned filter avoided 14,960,237 of 15,292,372 orbit-key
calculations (97.828%) on 24 one-target pairs. That figure belongs to its
historical source and filter geometry. The direct-aligned candidate packaged
here was freshly replayed on those 24 schedules: it avoided 14,921,205 of
15,292,372 orbit-key calculations (97.573%) and matched the archived direct
candidate on all 25 primary and replay targets. CPU wall times from that
Darwin host are exploratory under this repository's isolation rule.

## Build and replay the included witness

Check out `cryptanalysis` and `crypto` as sibling directories. The Cargo
dependency uses `../../../crypto` relative to this experiment. The two
imported `crypto` arithmetic modules and Cargo manifest match published
crypto commit `8ab924b935923df9faac25915ed7d9849974de0b`. The local build
also had two additional module declarations in `src/cryptanalysis/mod.rs`;
the [replay summary](replay/summary.json) records the exact dependency file
hashes, Git commit, and tracked dirty paths. Use that published revision for
a clean sibling checkout and rerun the correctness gates.
The [clean dependency receipt](clean_crypto_build.json) records a passing
release build and the included witness test against an exact `git archive`
of that published commit, with the checked source-file hashes and binary hash.

From the `cryptanalysis` root:

```sh
cargo test --release --offline --locked \
  --manifest-path experiments/a1-conjugate-bloom-20261009/Cargo.toml
```

The included [single-hit fixture](fixtures/single_hit.json) contains the
first verified A1 witness from attempt 39 of the original primary target.
The test independently reconstructs the difference x and its canonical key,
checks membership for all 53 inserted conjugates, verifies the exact pair
hit and weighted six-seed row, and replays the scalar to the public target.
It also checks a filter negative and forces a Bloom positive for an x absent
from the exact table; the latter must be rejected by exact lookup.

An independent checked-Sage replay of the same compact witness is included.
On this machine, use the repository's verified local launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info
/Volumes/SSD990/cryptanalysis/sage -python \
  /absolute/path/to/cryptanalysis/experiments/a1-conjugate-bloom-20261009/sage_replay.py \
  /path/to/new/sage-replay-result.json
```

The recorded [Sage receipt](sage_replay_result.json) and
[runtime information](sage_runtime_info.json) came from this repository's
checked local launcher. A clean PR checkout needs a compatible Sage runtime
for this optional independent replay. The script verifies the point equation,
53-fold Frobenius alignment, six-seed row, and target scalar independently of the
Rust implementation.

## Replay the archived target schedules with this binary

The [archive replayer](replay_archive.py) takes the frozen primary workload
and 24 disjoint one-target workloads from the included compact
[archive](archive). It
builds a fresh filter from the packed index, checks every inserted conjugate,
then runs this binary once per target. It compares each new raw result with
the archived source-bound receipt on status, attempt count, singleton count,
filter counts, orbit-key count, first witness, weighted row, and scalar. New
raw outputs, source/binary hashes, input hashes, and a comparison summary go
to a caller-specified directory. It does not overwrite archive files.

```sh
cargo build --release --offline --locked \
  --manifest-path experiments/a1-conjugate-bloom-20261009/Cargo.toml
python3 experiments/a1-conjugate-bloom-20261009/replay_archive.py \
  --binary experiments/a1-conjugate-bloom-20261009/target/release/a1-conjugate-bloom \
  --output-dir /path/to/new/replay-output
```

When `CARGO_TARGET_DIR` is set, pass its release binary with `--binary`.
The filter bit array is generated and checked, then left in the output
directory; it is not committed. The included witness test runs without the
packed index or filter artifact. The [fresh replay summary](replay/summary.json)
binds the new source and binary hashes, frozen input and historical receipt
hashes, and all 25 matched fields. The 25 new raw JSON results are beside it.
The archived checked-Sage receipts in `archive/results` bind the prior
source and witness inputs; they are historical evidence, while the new Sage
receipt covers the compact fixture. CPU timing claims require a paired
isolated-host measurement with the one-target accounting contract.

Check the committed receipts without rebuilding the binary:

```sh
python3 experiments/a1-conjugate-bloom-20261009/validate.py
```
