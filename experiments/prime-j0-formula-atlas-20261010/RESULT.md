# Point-only U14 tables remove the remaining orbit-digit array

Mode 129 computes the canonical orbit, rank, and nearest digit during
recoding, then uses the same fourteen four-limb affine point windows and
grouped gauge as mode 128. Temporary canonical digits are released
after point-table preparation. The retained table falls from
**65,188,008 to 64,314,112 bytes**, saving **873,896 bytes**. Relative
to the stored-code gauge mode 127, the two arithmetic formats together
save **6,116,848 retained bytes**.

## Correctness and resource results

| Check | Result |
| --- | ---: |
| Exhaustive radix-512 and radix-1024 residue comparisons | 1,310,720 / 1,310,720 matched digit, orbit ID, and unit code |
| Separately built affine point-table entries | Every entry matched |
| New post-implementation scalar holdout | 4,096 / 4,096 matched point, representative, all choices, additions, and gauge products |
| Independent binary point replay | First 128 / 128 new outputs matched |
| Frozen fixture | 129 / 129 expected points verified in each mode |
| Native release suite | 85 / 85 passed |
| Retained bytes, digit-array mode 128 | 65,188,008 |
| Retained bytes, point-only mode 129 | 64,314,112 |
| Exact retained-byte saving | 873,896 |
| Local one-process peak RSS, reference | 253,558,784 bytes |
| Local one-process peak RSS, candidate | 260,685,824 bytes |

The [input record](fresh-inputs.json) uses seed `20261010129` and fixes
4,096 unsigned scalars with SHA-256
`55b53a8c2199e1ca04d93139b7892aa0861aa5637f980a89c5f5804074e38a85`.
Their reduced values are unique and disjoint from the ten frozen prior
input panels. The [holdout log](native-holdout.log) retains paired
per-scalar gauge-product counts; their decoded-byte SHA-256 is
`b20c4acb460e8cc39b8a8afeb8baf81fa7c01adb25acf8a1ef4976c317850700`.
The implementation and [protocol](PROTOCOL.md) were committed as
`57a97cc7` before those inputs were generated.

The [verification receipt](verification.json) has SHA-256
`0ce039649302c16a20e076b19b8ae1b905e31425c54dcd42e2b026226378b278`.
It reports `status: passed`, no problems, 42 source/input hashes, 18 raw
output hashes, and release binary SHA-256
`afaafde3398857f75f0afe726f224da538ba6e28d005d1f9c729ff4ea75a0b43`.

The retained-byte saving consists of 873,824 bytes of released
canonical digit pairs and 72 bytes of smaller table structs. Peak RSS
in these two local processes moved in the opposite direction, a
diagnostic of allocation and host conditions rather than the logical
table size. Local CPU timer fields and preparation times are retained
as exploratory rows. A wall-time ratio requires the paired Linux
[isolation panel](ISOLATED_PANEL.md) with a passing host preflight and
noise gates.

The [x86 target check](x86-cross-check.json) passed a Rustup-stable
release compilation for `x86_64-unknown-linux-gnu` on this ARM64 macOS
host. Its source and log hashes mark it as a compile check; physical
x86 execution uses the separate serialized RunPod job.
