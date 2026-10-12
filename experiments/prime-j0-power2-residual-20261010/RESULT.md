# Twelve shift windows and an exact terminal residual

The radix-1024 format reconstructs every certified secp256k1 scalar with
twelve signed shift windows and one exact terminal Eisenstein pair. Its
exhaustive full atlas has 87,383 seeds; its finite terminal disk has 10,061.
The independent verifier checks all 1,048,576 residue codes and 80,521
terminal pairs, including minimal seed counts for the declared unit and tau
cover. The proof and binary hashes are in [PROOF.md](PROOF.md) and
[atlas-receipt.json](atlas-receipt.json).

The fresh panel contains 4,096 full-range scalars, drawn after the format,
atlases, and input law were frozen. It is disjoint from the previous panels
named in [fresh-inputs.json](fresh-inputs.json). Independent affine replay
verified scalar reconstruction, each term, the two tau buckets, grouped
unit gauges, and binary scalar multiplication for every scalar. The
radix-944 control replayed on the same panel and matched the output digest.

| Frozen-panel diagnostic | Radix-944 control | Radix-1024 terminal residual |
| --- | ---: | ---: |
| Scalars | 4,096 | 4,096 |
| Affine table slots | 993,953 | 1,058,657 |
| Native retained bytes | 71,450,736 | 72,663,424 |
| Mixed additions | 49,152 | 49,152 |
| Grouped gauge rotations | 14,815 | 14,776 |
| Output SHA-256 | `e6c9e18553bcdd581725a66967fd8dcb735f5e17b44ba0746bdd48bb765e9f57` | same |

The native Rust test compared both modes on the same 4,096 scalars and
checked the first 128 against independent binary multiplication. Its
radix-1024 decoder, table construction, and point kernel passed. The
candidate uses 1,212,688 additional retained bytes while replacing the
radix-944 quotient path with signed power-of-two shifts. The addition count
is unchanged and the grouped gauge count falls by 39 on this panel. Those
operation counts identify the precise experiment for a paired runtime
comparison; they are not a wall-time ratio.

The separate native crate is assembled from the pinned radix-944 source
through [materialize_native.py](materialize_native.py), the
[native delta](native-delta.patch), and the two binary atlases. The Linux
replay script records source identity, host probe, complete Rust test output,
and edge fixture verification. CPU timing can be promoted only with the
host-level isolation record required by `docs/ISOLATED_BENCHMARKS.md`.
