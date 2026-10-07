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
fixture for training and was committed before generating new inputs. The
training model checked every scalar identity and found no capacity
overflow at those lengths:

| Curve | Previous single-window adds | Hexagonal pair adds | Saved in model | Prepared point slots | Point-table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 54,929 | 32,735 | 22,194 | 22,122 | 707,904 |
| `j0-56` | 114,225 | 65,449 | 48,776 | 44,244 | 1,415,808 |

The static digit, representative, and action arrays occupy 306,900
bytes. Prepared point memory is much larger than the 9,088 and 15,904
bytes of the previous packed single-window tables. The complete point
preparation cost, memory peak, online integer work, and wall time must be
measured before this can be called faster. The operation model is a
prediction; a disjoint correctness panel and a qualifying isolated-host
receipt are separate gates. This is a variable-time public-scalar
scheme, not a one-target rho or IC speedup result. The combination is
new in this repository; academic novelty is not established.
