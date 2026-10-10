# Arithmetic orbit indexing saves 5,242,952 retained bytes in U14

Mode 128 computes the six-unit orbit ID and action code from the residue
pair, using the row-rank formula in the [proof](PROOF.md). It retains the
same four-limb affine point table and grouped-gauge accumulation as mode
127. This removes the full stored residue-code atlas while preserving
the fourteen digit and point choices.

## Correctness and resource results

| Check | Result |
| --- | ---: |
| Exhaustive radix-512 and radix-1024 residue comparisons | 1,310,720 / 1,310,720 matched digit, orbit ID, and unit code |
| Separately built affine point-table entries | Every entry matched |
| New post-implementation scalar holdout | 4,096 / 4,096 matched point, representative, all choices, additions, and gauge products |
| Independent binary point replay | First 128 / 128 new outputs matched |
| Frozen fixture | 129 / 129 expected points verified in each mode |
| Native release suite | 83 / 83 passed |
| Retained bytes, stored-code mode 127 | 70,430,960 |
| Retained bytes, arithmetic mode 128 | 65,188,008 |
| Exact retained-byte saving | 5,242,952 (7.44%) |
| Local one-process peak RSS, reference | 257,933,312 bytes |
| Local one-process peak RSS, candidate | 249,708,544 bytes |

The [input record](fresh-inputs.json) uses seed `20261010128` and fixes
4,096 unsigned scalars with SHA-256
`d8a50499880df3ffef7fa6aae4793dd6b4637d4f8e92161d990e395419f9b25b`.
Their reduced values are unique and disjoint from the nine frozen prior
input panels. The [holdout log](native-holdout.log) contains the paired
per-scalar gauge-product counts; their decoded-byte SHA-256 is
`7f3b5ec3051cbb84d3602dbb78afe268ebe7ad46a9818c34ca2b66a26b9ab0e8`.
The prior stored-atlas gauge proof and beta-product bound apply unchanged.

The [verification receipt](verification.json) has SHA-256
`d6c4106e9bc816f35f5c9ff387391a82d18529531b482a98da6f12a8da8a9a4f`.
It reports `status: passed`, no problems, 35 source/input hashes, 20 raw
output hashes, and release binary SHA-256
`efde95cec4fa2a5890282db92d6d917e13a2e00a6b9e288820e7575fd7bec0ec`.
The failed first holdout compile is retained with its exit code and log;
it was caused by a test-only `PartialEq` assumption and was corrected
before the successful holdout and full suite.

The [x86 target check](x86-cross-check.json) passed a release compilation
for `x86_64-unknown-linux-gnu` using the Rustup stable compiler on this
ARM64 macOS host. Its source and log hashes distinguish this compile
check from physical x86 execution, which remains in the serialized
remote queue.

The local process RSS and timer rows in the raw resource files are
diagnostics from a contended macOS host. The exact retained-byte saving
follows from removing `4*(512²+1024²)` residue-code bytes and 72 struct
bytes. A CPU wall-time comparison requires the paired Linux
[isolation panel](ISOLATED_PANEL.md) and a host that passes its preflight
and noise gates. The existing serialized RunPod container can supply
physical x86 correctness checks but lacks that host-level isolation.
