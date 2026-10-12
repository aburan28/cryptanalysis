# Native radix-152 axis table and public-point replay

The opt-in native evaluator stores the complete sixteen-window
radix-152 format in **4,568,960 retained bytes** on the local ARM64
build. This includes 69,698 affine point entries, the 23,104-residue
atlas, canonical digits, table containers, and unit constants. Its
point payload alone is 4,460,672 bytes. The retained allocation is
23,988,048 bytes below the recorded radix-416 native allocation on
the same host and source family.

The evaluator is built in a disposable crate overlay; the shared native
source is copied and left intact. The [overlay record](native-overlay-record.json)
hashes the original and inserted Rust sources. The local build used
Rust 1.93.1 on macOS ARM64; the [build receipt](native2-local-build.json)
records binary SHA-256
`6c5ba6423956436e04c9f6f7a4e3ebb3019d47297089e34c8d54efb316321023`.
The evaluator exhaustively checked all 23,104 ordinary residues,
matched the frozen canonical-digit SHA-256
`8b7dd9754725d7d573bb2b9a0e25aac95ae5b137def2f83beb94f08681d815c1`,
and verified the 69,698-entry table count.

The native evaluator and the second holdout generator and checkers were
frozen together at `afd9c6eb43b9e318bc82084767e6201bd9f97379`
before the second input draw. The [second fixture](holdout2.json)
contains 512 distinct scalars, disjoint from the design panel, first
holdout, and listed earlier panels. An independent projective binary
multiplier generated the expected public points; a separate affine
group law replayed every selected term. Native output matched all
**512 / 512** points and the independent stream digest
`8da3c15756f1d42392720c6e44d642aee2cafe95e2c399cff5216af9742992e6`.

| Second-panel measure | Value |
| --- | ---: |
| Selected terms | 9,216 |
| Native point additions | 8,704 |
| Native gauge rotations | 1,022 |
| Atlas residues audited | 23,104 |
| Public points verified | 512 / 512 |

The [independent receipt](holdout2-replay.json),
[native receipt](native2-replay.json), and [per-case native rows](native2-rows.jsonl)
retain source and input hashes, every output point, and operation counts.
The first source-frozen independent panel also passed the native
implementation as a development control. Table addresses depend on the
public scalar. A controlled CPU timing comparison requires paired
complete operations and a passing host-isolation receipt.
