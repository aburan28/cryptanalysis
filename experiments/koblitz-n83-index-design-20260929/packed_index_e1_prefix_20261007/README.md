# E-1: bounded N83 packed S3 root-index experiment

The frozen Q1325 factor base and one ordinary N83 target were used for a
paired root-index stage comparison. This is proposal `Q2026100701` with
`candidate_id: null` and `run_id: null`: no factor-base log matrix or target
DLP was solved. The [protocol](protocol.json), [workload](workload.json),
[manifest](stage_manifest.json), six raw `run_*.json` records, and
[summary](summary.json) retain the inputs, limits, source hashes, failures,
and measurements.

Both backends compute the same S3 roots for the same 2,000,000 sampled pair
states and probe one Frobenius orientation of each state against the same
target. The hash backend keeps the first witness for each canonical key in
an open-addressed table. The packed backend stores every root as an 18-byte
record: an 11-byte exact 83-bit key and a 7-byte descriptor containing a
42-bit offset in the satisfiable-state vector, a root selector, and a 7-bit
canonical shift. It sorts the records and builds a 20-bit key-prefix directory
of 64-bit offsets. The first record for a key reproduces the hash backend's
first-inserted witness. The state-vector offset differs from the absolute
pair-state ID in the earlier storage model; the state vector remains resident
for target queries in both arms.

| Paired stage metric, median of 3 each | Hash | Packed with prefix |
| --- | ---: | ---: |
| Root-table allocation | 192.0 MiB | 76.7 MiB |
| Peak process RSS | 662.2 MiB | 478.6 MiB |
| Index build | 4.562 s | 2.412 s |
| Target-dependent probe stage | 8.468 s | 11.914 s |
| Target lookup comparisons/probes | 18,616,995 | 58,251,024 |

The paired order was hash, packed, packed, hash, hash, packed. The target
stage ranges were 7.816–9.038 s for hash and 10.805–13.310 s for packed.
All six runs examined 2,000,000 satisfiable index states, produced 4,000,000
distinct root keys, scanned 2,000,000 target orientations, and ended with
zero table hits and zero verified relations. Their arithmetic operation
counts and 64 first-witness lookup controls agree exactly. The packed index
saves 2.50× in allocated table bytes here, but its target probe stage was
1.41× slower by the median. These CPU ratios are exploratory: no host-level
isolation receipt was obtained. Full single-target online time, rho time,
and IC speedup remain unknown.

The [native source](native_packed_index.rs) is a copy of the frozen Q1335
stage with the backend selection and packed index added. Its two unit tests
cover batched S3 roots and packed duplicate/first-witness behavior. The
frozen input representative file and bridge are verified by SHA-256 before
building. In a fresh sibling copy of this directory, `python3 run.py`
regenerates the protocol, builds the Rust binary, runs all six paired
measurements, and checks every cross-mode invariant. The frozen runner uses
fixed result filenames, so running it in this directory would replace these
receipts.
The build receipt records the physical host description, Rust toolchain,
binary hash, and missing isolation receipt; the protocol records the runner
and library source tree hashes.

An earlier development run without `serde_json` arbitrary precision failed
before index construction. The first runner overwrote its stderr files when
rerun, so the [failure note](development_failure.json) is retrospective and
is not a raw receipt. It is excluded from the table above.
