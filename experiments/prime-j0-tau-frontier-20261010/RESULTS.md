# Two-bucket scalar table storage frontier

Exact cycle-cover atlases and mixed-width radix schedules reduce the
fixed-base secp256k1 table from 8,336,160 bytes at sixteen windows to
**4,552,716 bytes at seventeen windows**. Eighteen and nineteen windows
reduce it further to 2,805,196 and 1,511,564 bytes, respectively. Each
total includes all affine point payloads and distinct 32-bit atlas
allocations before native container metadata.

| Windows | Width schedule | Point slots | Point bytes | Atlas bytes | Sum |
| ---: | --- | ---: | ---: | ---: | ---: |
| 16 | `8×15, 9` | 107,814 | 6,900,096 | 1,436,064 | 8,336,160 |
| 17 | `7×6, 8×10, 7` | 64,463 | 4,125,632 | 427,084 | 4,552,716 |
| 18 | `7×14, 8×3, 7` | 37,158 | 2,378,112 | 427,084 | 2,805,196 |
| 19 | `6×3, 7×15, 6` | 21,949 | 1,404,736 | 106,828 | 1,511,564 |

Every listed schedule has a 129-bit radix product and an exact positive
termination margin. The final-row digit limits are 363, 90, 90, and 44
in table order; nonfinal limits equal their radices. The screen covers
widths 6–9 and 16–19 windows under those nonfinal limits. The selected
17–19-window atlases decoded all residues, and each layout reconstructed
all 8,192 scalars from the two frozen prior panels. Source and input
hashes, class counts, and raw construction counts are in
`screen-result.json` and `atlas-replay.json`.

The seventeen-window format adds one selected table term relative to
the sixteen-window format while cutting construction storage by 45.4%.
Its independent affine secp256k1 replay passed all 8,192 prior panel
scalars against binary multiplication; `group17-check.json` binds the
verifier source, atlas, and panel hashes. Native table construction and
a new disjoint panel are the next correctness gates. Paired online
timing on a host passing the repository isolation gate will determine
whether the smaller table also reduces wall time after all additions,
bucket work, and inversion are charged.
