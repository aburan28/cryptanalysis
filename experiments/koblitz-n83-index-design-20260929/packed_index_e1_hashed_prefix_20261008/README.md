# E-1 follow-up: hashed prefix for the packed N83 root index

This stage experiment compares two lookup directories over the same sorted
18-byte N83 root records. The first E-1 run showed that the packed table
used less memory than the open-addressed table but took longer to probe.
Canonical Frobenius rotation chooses the minimum 83-bit key, so its leading
bits are biased toward zero. A directory indexed by the leading 20 bits can
leave many records in one bucket.

The `packed` mode sorts by the exact key and uses those leading 20 bits.
The `packed_hashprefix` mode sorts by a 20-bit mix of the exact key, then by
the exact key and descriptor. Both modes keep every root, use the same
20-bit offset directory and binary search, and return the first inserted
witness for an exact key. The mixed prefix changes only bucket placement;
the full 83-bit key is still compared before accepting a hit.

The [protocol](protocol.json), [workload](workload.json), [stage manifest](stage_manifest.json),
six raw run records, and [summary](summary.json) freeze one N83 target and
2,000,000 sampled index states. The paired order is `packed`,
`packed_hashprefix`, `packed_hashprefix`, `packed`, `packed`,
`packed_hashprefix`. Source hashes and the frozen `crypto` dependency commit
are in the protocol. The runner archives that commit from a local crypto Git
checkout, verifies the resulting source tree, and builds against the frozen
copy. Set `CRYPTO_REPO` to the checkout path if it is not
`/Volumes/SSD990/crypto`.

| Paired stage metric, median of three runs per mode | Raw prefix | Hashed prefix |
| --- | ---: | ---: |
| Exact-key lookup comparisons | 58,251,024 | 25,265,242 |
| Root-table allocation | 76.7 MiB | 76.7 MiB |
| Index build, target independent | 9.389 s | 15.170 s |
| Target-dependent probe stage | 36.743 s | 33.657 s |

The hash prefix reduced exact-key comparisons by 2.31× without changing
table allocation. All six runs examined the same states, produced the same
4,000,000 distinct root keys, and returned identical first-witness controls,
operation counts, zero table hits, and zero relations. The target-stage
ranges overlap: 29.777–49.923 s for the raw prefix and 33.634–40.989 s for
the hashed prefix. This busy-host timing is exploratory; the comparison
establishes less lookup work, but it does not establish a controlled CPU
speedup. Hashed-prefix sorting also increased the measured index build cost.

To replay, copy this experiment directory alongside the committed E-1
directory and frozen parent inputs, then run `python3 run.py` in the copy.
The runner writes fixed result filenames and would replace the published
receipts if run in this directory.

This is a bounded point-decomposition stage measurement with
`candidate_id: null` and `run_id: null`. It does not solve the target DLP or
support an IC speedup claim. CPU timing ratios remain exploratory without a
host-isolation receipt.
