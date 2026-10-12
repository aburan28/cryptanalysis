# Canonical Karatsuba Solinas radix-152 scalar evaluator

The opt-in candidate retains the radix-152 format's **69,698 affine point
entries** and **4,568,960 retained table and atlas bytes** while replacing
Montgomery XYZZ arithmetic with canonical Karatsuba Solinas XYZZ arithmetic.
On the new frozen 512-scalar panel, its ordinary-path source model uses
**1,409,024** 64-bit products versus **3,156,992** for the merged XYZZ
reference: **1,747,968 fewer**, or **55.368%** of this counted boundary.
The reference and candidate selected the same terms and returned the same
public point for every case.

| Frozen replay | Prior control | New holdout |
| --- | ---: | ---: |
| Public secp256k1 scalars | 512 | 512 |
| Reference, candidate, and independent expected points equal | 512 | 512 |
| Noninitial mixed additions | 8,703 | 8,704 |
| Nonzero unit rotations | 1,023 | 1,024 |
| Reference ordinary-path 64-bit products | 3,156,609 | 3,156,992 |
| Candidate ordinary-path 64-bit products | 1,408,848 | 1,409,024 |
| Retained table and atlas bytes | 4,568,960 | 4,568,960 |

The implementation and replay scripts were frozen at commit `a6dad2140`
before seed `20261012234` generated the new panel. Its fixture SHA-256 is
`9e268f18783b3d2c649c8fc8cc0b50a8926dfe4ebb2096fe03345a1ece13c507`;
the independent point-stream SHA-256 is
`a40763b319c814d3b6131f30dd22dbb6df3338b61fa8c9a960237507a2d70e73`.
The generator checks disjointness against five earlier public panels.
`replay.json` binds portable source, fixture, output, count, and table-size
digests. `model.json` binds the exact native and Montgomery source files
and the count calculation. The existing radix-152 scalar and field proofs
and the new source-count identity are mapped in `PROOF.md`.

The same portable replay passed in a cached offline Linux ARM64 Rust 1.93.1
container. The candidate release binary SHA-256 there is
`ac643745a0145496934afe20617d9ac1e9df2277ed2e7e4fea03dad3b5acfea0`;
the reference binary SHA-256 is
`56e435411b4b8f9cf81efea9527b242b2ee3c85c5852a818d750245f7571c35b`.
The container image, locked build flags, binary hashes, and replay digest
are in `linux-build.json`; the macOS ARM64 build identities are in
`local-build.json`. Eight boundary
inputs, including zero, the subgroup order, and the largest 256-bit scalar,
also matched the reference and independent expected points. The first
temporary boundary fixture lacked its required `schema` field and stopped
at input validation; after adding that field, all eight cases passed. An
optional repeat of the macOS replay was interrupted during a contended
reference process; the completed source-bound write and Linux `--check`
above are the retained correctness results.

The source model charges ordinary nonexceptional mixed additions and unit
rotations. It excludes recoding, lookup, exceptional branches, final
inversion, and CPU effects. A complete-operation paired run with a passing
host-isolation receipt is the next performance gate for this format.
