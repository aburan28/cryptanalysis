# Radix-152 axis-factorized scalar format

Sixteen radix-152 unit-orbit windows and two bounded terminal axes cover
the complete secp256k1 scalar range with **69,698 affine point entries**.
At 64 bytes per point, their payload is **4,460,672 bytes**. The exact
bound-based census selects radix 152 uniquely among all integer radices
at least two for this sixteen-window construction. Lean checks the
universal digit bound, terminal bound, scalar reconstruction, unit-sector
selection, and axis factorization.

| Frozen design measure | Radix 416, 13 windows | Radix 152, 16 windows |
| --- | ---: | ---: |
| Scalar cases | 4,096 | 4,096 |
| Affine point entries | 433,578 | **69,698** |
| Point payload bytes | 27,748,992 | **4,460,672** |
| Selected terms | 61,440 | 73,726 |
| Ordinary residues audited | 173,056 | 23,104 |

The format removes **363,880 stored points**, or **23,288,320 point
payload bytes**, relative to radix 416 and selects 12,286 more terms on
the paired design panel. Its ordinary tables contain `16*3,852=61,632`
point entries; the two terminal axes contain 4,840 and 3,226. Every
design scalar reconstructed its pinned Eisenstein representative. The
[proof map](PROOF.md), [search receipt](search.json), and
[design receipt](design.json) retain the exact assumptions, per-radix
census, source hashes, atlas digest, and paired selected terms.

The first post-replay-source holdout is disjoint from the listed prior
panels. Its 512 expected public points matched a separate affine group
replay and the opt-in native evaluator. It selected 9,216 terms against
7,680 for radix 416 on the identical scalars. The point-stream digest is
`e67942606b1b71f33c641d3e66dfb8862be3dac407d26126419d830342cd6517`.
The native build retained **4,568,960 bytes**, including the atlas,
ordinary tables, terminal axes, and unit constants. The
[independent replay](holdout-replay.json) and
[native replay](native-replay.json) bind sources, inputs, table counts,
and every public point.

The next gate is a second disjoint public-point panel drawn after the
native source freeze. A matched complete-operation run on a qualifying
isolated host will determine the CPU timing tradeoff.
