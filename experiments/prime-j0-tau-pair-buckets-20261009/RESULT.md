# Two-bucket tau-orbit fixed-base scalar format

The radix-1021 atlas covers every residue class with a unit image of either a
stored seed or its tau image. It stores **93,777 seeds per row** across thirteen
rows and folds selected points as `B0 + tau(B1)`. The native retained payload
is **92,320,448 bytes**, **2,051,392 bytes below** the 90 MiB cap. This removes one
nontrivial tau map and one projective bucket merge from the three-bucket
format's common full-width execution path, while storing 203,749 more points.

The [protocol](PROTOCOL.md) was committed as `d6dde405c` before the full
atlas screen. The minimum cycle cover has 13,813 length-one and 79,964
length-two segments. The [screen receipt](screen-result.json) records all
5,121 tau cycles in the six-unit quotient, a complete check of **1,042,441**
residues for unique code assignment, exact congruence, and digit norm at most
`840^2`, and the exact thirteen-window termination inequality. The seven
boundary and 512 seeded scalar representatives reconstructed exactly. The
point map is [atlas.bin](atlas.bin); its SHA-256 is
`5b6a368170700062365e51ebc5e601daacfdf4a233006c5469ec64f38a22f690`.

For the declared shortest-seed and exponent-`{0,1}` alphabet, the cycle DP
finds the minimum possible number of stored seeds. On a linearized cycle
`v_0,...,v_(m-1)`, set `F(m)=0` and
`F(i)=1+min(F(i+1), F(i+2))`, admitting the second term only when the seed at
`v_i` can cover two nodes and `i+2<=m`. Every circular cover has a segment
containing node zero that starts at zero or at its predecessor. Cutting at
that segment start makes the cover linear, so checking those cuts and taking
the smaller `F(0)` is exact. The implementation also checks one redundant
third cut for consistency with the three-bucket generator. This optimality
is within the frozen seed alphabet; different digit representatives or
additional online endomorphisms define different design spaces.

| Format | Windows | Seed points per row | Retained payload | Bucket maps and merges |
| --- | ---: | ---: | ---: | --- |
| U14 reference | 14 | mixed radix | 78,470,208 bytes in the current binary | none |
| Three-bucket tau orbit | 13 | 78,104 | 77,587,820 bytes in the prior binary | at most two tau maps and two projective merges |
| Two-bucket tau orbit | 13 | 93,777 | 92,320,448 bytes in the current binary | at most one tau map and one projective merge |

Across the frozen 519-scalar input record, the two-bucket screen selected
6,661 nonidentity points. Bucket occupancy gives **5,632** nominal mixed
additions, **512** nominal projective merges, and **512** nontrivial tau maps
before possible point cancellation. The corresponding three-bucket counts
were 5,178 mixed additions, 966 nominal merges, and at most 967 nontrivial
tau maps. The two-bucket cover exchanges 454 within-bucket mixed additions
for 454 fewer nominal projective merges and up to 455 fewer nontrivial tau
maps on these frozen inputs. Full CPU cost also includes recoding and random
table access.

The [source-bound native receipt](verification.json) passed **66 release
tests**, including independent group sums for all **1,219,101** stored point
slots. Both U14 and two-bucket fixture modes verified all **129** expected
points. The new format matched U14 and the three-bucket mode on all **519**
frozen scalar inputs; **128** fresh points also matched an independent binary
double-and-add evaluator. The release binary SHA-256 is
`47db0a893aca976a7ec7ef7cd0976b7ae72caf1857ef1209a32710ce2d3c5e6e`.
The 48-byte difference from the screen's 92,320,400-byte estimate is actual
Rust table metadata. The receipt retains source, input, atlas, binary, raw
command output, and exit hashes.

The same-binary [isolated panel](ISOLATED_PANEL.md) pairs this candidate with
U14 on nine frozen fixture cases and five repetitions. It passed local schema
validation; the local manifest SHA-256 was
`10ca1bc859eb57155cd40a9bc5ed6d4770a7beb834496a51b298f138f28004d0`.
The reachable RunPod CPU Pod fails the
[host isolation gate](../../docs/ISOLATED_BENCHMARKS.md), so the next empirical
step is a complete paired online run on a qualifying host.
Endomorphism digit sets and bucket accumulation have prior art; the exact
cycle-cover construction and this fixed-base combination need independent
priority review before an academic novelty statement.
