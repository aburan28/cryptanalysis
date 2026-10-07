# Unit-closed hexagonal two-window scalar table

The [zero-window experiment](JOINT_WINDOW4_ZERO.md) changes the GLV
representative to remove one joint radix-16 digit. For the `j0-56`
subgroup, there are at most `256^7 - 255^7` seven-window digit strings
with any zero joint digit. Even if every such string names a distinct
subgroup element, they cover no more than
`(256^7 - 255^7) / 53624256071278747 = 3.632%` of the group. Thus a
seven-window scheme that saves an addition only by making a joint digit
zero cannot provide a large uniform gain on that curve.

This experiment changes the point-table format. The unit group of the
Eisenstein integers acts on a coefficient pair by sign and by
`(x,y) -> (-y,x-y)`. Modulo 16, the 256 residue classes form 44 orbits:
one zero orbit, one orbit of size three, and 42 of size six. The
[map producer](make_joint_pair_map.py) selects the least-norm integer
representative for each nonzero residue orbit and includes all six unit
images. The resulting **259-digit alphabet is closed under all six
units** and covers every residue class. Only `(8,0)`, `(0,8)`, and
`(8,8)` have two choices; the frozen recoder chooses the preferred digit
specified by the producer.

For adjacent digits `d0`, `d1`, one table point represents the Eisenstein
coefficient `d0 + 16 d1`. The unit-closed alphabet gives 66,367 distinct
two-window coefficients, with **11,061 nonidentity unit orbits**. A
65,536-entry static map converts the two residue codes to an orbit index
and unit action. Each prepared point stores `x`, `y`, and `βx` in one
32-byte slot, reconstructing the other unit images as in the packed
two-coordinate plane. One online mixed addition handles each nonzero
two-window coefficient. Four hexagonal digits use two pair slots on
`glv-j0-32`; eight digits use four pair slots on `j0-56`.

The [frozen design](joint-pair-design.json) used the earlier zero-window
fixture for training and was committed as `bfb2f050` before generating
[new disjoint inputs](joint-pair-inputs/inputs.json). The
training model checked every scalar identity and found no capacity
overflow at those lengths:

| Curve | Previous single-window adds | Hexagonal pair adds | Saved in model | Prepared point slots | Point-table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 54,929 | 32,735 | 22,194 | 22,122 | 707,904 |
| `j0-56` | 114,225 | 65,449 | 48,776 | 44,244 | 1,415,808 |

The [release panel](joint-pair-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-ubsan-panel.json) each have 24
verified arms in rotating order: hexagonal pair, packed single-window
plane, and fixed comb9. Every native arm replayed all 4,096 outputs per
case. An independent Python model checked all 32,768 scalar identities,
184 group decompositions, both operation counts, and the unit action
costs. The C suite passed 2,312,247 checks in both builds, including
full point-table verification on each curve and forced fallback.

| Curve | Packed plane online adds | Hexagonal pair online adds | Saved | Hexagonal preparation adds per base | Hexagonal point-table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 54,979 | 32,726 | 22,253 (40.48%) | 22,798 | 707,904 |
| `j0-56` | 114,224 | 65,439 | 48,785 (42.71%) | 45,596 | 1,415,808 |

Each row aggregates 16,384 fresh public scalars across four base points;
the preparation count is for one base point and is repeated for each of
those four cases. Both modes had zero capacity fallbacks. The pair table
needs two or four batch inversions, respectively, and 306,900 bytes of
static digit, representative, and action arrays. Its prepared point
memory is much larger than the 9,088 and 15,904 bytes of the previous
packed single-window tables. The [isolated manifest
producer](make_joint_pair_isolated_manifest.py) binds the exact sources,
inputs, modes, and expected output digests for a qualifying physical
host; its local schema preflight covers 152 artifacts, eight cases, and
24 paired repetitions.

Preparation adds exceed the online additions saved in each 4,096-scalar
case. Using the observed per-scalar saving, the extra preparation-add
count would break even at roughly 16,559 scalars per fixed base on the
small curve and 15,125 on the large curve. This is only an addition-call
calculation: projective preparation additions, online mixed additions,
inversions, memory traffic, and field operations have different costs.

These counts prove fewer table additions under the frozen public-scalar
workload. They do **not** prove lower wall time: preparation, memory
traffic, online integer work, and cache behavior matter. Local macOS
timing fields are exploratory. This is not a one-target rho or IC speedup
result. Symmetric Eisenstein digit sets and unit actions appear in
[Heuberger and Mazzoli's scalar-multiplication work](https://pmc.ncbi.nlm.nih.gov/articles/PMC4144834/).
The adjacent-pair table here is a new combination in this repository;
academic novelty is not established.
