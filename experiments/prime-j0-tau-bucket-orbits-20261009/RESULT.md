# Tau-bucket orbit atlas for fixed-base secp256k1 multiplication

The thirteen-window radix-1021 atlas stores **78,104 seed points per row**.
Each residue selects a unit image of a seed, `tau(seed)`, or `tau^2(seed)`.
The evaluator sums selected points in three exponent buckets and folds them
as `B0 + tau*(B1 + tau*B2)`. This keeps the online endomorphism count bounded
by two tau maps per scalar while retaining at most thirteen point selections.
The native retained payload is **77,587,820 bytes**, below the 90 MiB cap.
That is **65,285,924 bytes (45.69%) less** than the radix-943 thirteen-window
table's 142,873,744 bytes, with the tau maps and projective merges charged
to this format's online work.

The [protocol](PROTOCOL.md) was committed as `a55c577eb` before the atlas
screen. Its exact cycle cover found 5,121 tau cycles in the six-unit quotient
of the 1,042,441 residue classes. The cycle lengths were one, 17, and 34.
The 78,104 selected segments comprise 10,368 length-one, 39,835 length-two,
and 27,901 length-three segments. The screen checked every residue for a
unique code, exact congruence, and digit norm at most `840^2`; it checked the
strict integer termination inequality for thirteen windows. The frozen
seven boundary and 512 seeded full-range scalars reconstructed exactly.
The [screen receipt](screen-result.json) binds the residue map, atlas binary,
screen source, and input digest. The atlas itself is [atlas.bin](atlas.bin).

| Format | Windows | Selected points per scalar | Point additions before bucket maps | Declared retained payload |
| --- | ---: | ---: | --- | ---: |
| U14 reference | 14 | at most 14 | at most 13 mixed additions | 78,470,208 bytes in the current binary |
| Tau-bucket atlas | 13 | at most 13 | within-bucket mixed additions plus projective bucket merges and two tau maps | 77,587,820 bytes in the current binary |

The [source-bound native receipt](verification.json) passed **64 release
tests**, including an independent group-sum check of all **1,015,352** stored
point slots. Both U14 and tau-bucket fixture modes returned all **129**
expected points. The tau-bucket mode also matched all **519** frozen boundary
and fresh scalar results from the radix-943 reference; **128** fresh points
matched a separate binary double-and-add evaluator. The release binary
SHA-256 is `e75a393244447a06282f679f9ac3ae2c439171e720b2bf09f0d4294e633b4fe3`.
All commands, source and input hashes, raw outputs, exits, and preparation
memory fields are in that receipt. The native payload count exceeds the
screen's 77,587,780-byte estimate by 40 bytes of actual Rust metadata.

Across the 519 frozen scalar inputs, the residue screen selected 6,661
nonidentity points, giving 5,178 nominal within-bucket mixed additions and
966 nominal projective bucket merges. The Horner fold needs at most two tau
maps per scalar; bucket occupancy gives an upper bound of 967 nontrivial
maps across this panel before possible point cancellation. These are
operation counts, including boundary cases, rather than a CPU
timing result. The paired [isolated panel](ISOLATED_PANEL.md) has nine cases
and five repetitions and passed local schema validation with the verified
same binary. Its local manifest SHA-256 was
`b343e3cc241dcbbb0a137784b772a58e14e8e1bc33e1518f8729972930c172b2`.

The online comparison must charge recoding, table traffic, the bucket
endomorphism maps, and projective merges. The available RunPod CPU Pod fails
the [host isolation gate](../../docs/ISOLATED_BENCHMARKS.md), so the next
measurement is a complete paired online panel on a qualifying host. A
stage count cannot determine whether the added bucket work is offset by
fewer selected points or different table access.

Endomorphism digit sets, tau-adic expansions, and unit-based precomputation
have prior art. A specific novelty claim for this cycle-cover/bucket
combination needs an independent literature review beyond this initial
screen and native implementation.
