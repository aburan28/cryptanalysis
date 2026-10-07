# Packed two-coordinate unit plane for joint Eisenstein digits

For a `j=0` curve, the order-three endomorphism acts on an affine point as
`(x,y) -> (βx,y)`, where `β²+β+1=0` in the field. The [selected joint
table](JOINT_WINDOW4_HOT.md) stores one point per digit orbit and applies
`β` or `β²` to its x coordinate during the online multiplication. This
experiment stores both `x` and `βx`. The third orientation is reconstructed
as `β²x = −x − βx`, using one field addition and one negation. Sign actions
still negate `y`.

The implementation uses a **private** four-word table record
`(x, y, βx, identity)`. It converts that record into a canonical `ca_elem`
before any group operation. A normal `ca_elem` also occupies four 64-bit
words, with its fourth word fixed to zero, so the persistent table has the
same byte count and number of point slots as the selected joint table. The
conversion temporarily holds both tables during preparation. This layout is
variable-time and intended only for public scalars. It does not change the
group's public `ca_elem` format or FFI representation.

The [algebraic design](joint-window4-plane-design.json), [design producer](make_joint_window4_plane_design.py),
packed layout, and [fresh-input generator](make_joint_window4_plane_inputs.py)
were committed in `460f7d07` before the new scalars were generated. The
[fixture](joint-window4-plane-inputs/inputs.json) contains 32,768 scalars
across eight cases and excludes the ten earlier fixtures. It reuses the
exact selected representatives and action map from [the preceding
design](joint-window4-hot-design.json), changing only table storage and unit
application.

The [release panel](joint-window4-plane-native-panel.json) and
[warnings-as-errors UBSan panel](joint-window4-plane-ubsan-panel.json) each
ran 24 arms in rotating order: packed plane, selected joint table, and fixed
comb9. Every native arm verified all 4,096 outputs per case. The independent
Python model checked all 32,768 scalar identities and 184 group outputs.
Preparation verification checks every packed table point against an
independent scalar multiplication, checks each stored `βx`, and confirms
`−x−βx = β²x`. Release and UBSan `test_curve` each passed 2,312,099 checks,
including exact-curve identity cases, a corrupted companion coordinate, and
forced capacity fallbacks.
All held-out arms had zero fallbacks. The large curve still uses a checked
generic fallback because seven-window coverage has not been proved for every
scalar.

The counts below aggregate 16,384 scalar multiplications per curve. The
mixed-addition counts are identical within each paired curve. “Unit adds”
counts the modular addition and negation used for each `β²` orientation;
the base evaluator reports its unit field multiplications as “rotations.”
Preparation multiplications are per prepared base point.

| Curve | Mode | Point slots | Persistent point bytes | Preparation unit multiplications | Online mixed additions | Online unit multiplications | Online unit adds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | packed plane | 284 | 9,088 | 284 | 55,124 | 0 | 23,354 |
| `glv-j0-32` | selected joint | 284 | 9,088 | 0 | 55,124 | 25,466 | 0 |
| `j0-56` | packed plane | 497 | 15,904 | 497 | 114,211 | 0 | 57,318 |
| `j0-56` | selected joint | 497 | 15,904 | 0 | 114,211 | 57,063 | 0 |

Both modes use the same 1,308-byte static selected-orbit map. The plane
needs one additional temporary point-table allocation during preparation:
9,088 or 15,904 bytes, freed before online evaluation. Preparation also
retains the selected table's point additions, doublings, batch inversion,
and 32 or 56 unit rotations. The plane adds 284 or 497 setup field
multiplications to construct `βx`. The online evaluator replaces all unit
field multiplications with table reads or cheap field arithmetic. Its actual
CPU ordering is **unknown** until paired runs produce a qualifying
host-level isolation receipt. Local macOS timing fields are exploratory.
This is a repeated public-scalar workload, not a one-target DLP or rho
result.

The [isolated manifest producer](make_joint_window4_plane_isolated_manifest.py)
pins the fixture, same binary, selected and plane modes, source hashes, and
expected output digests. Its schema validates locally. A qualifying physical
Linux host is still required to measure a controlled wall-time ratio.

[Pasta curves' GLV implementation](https://docs.rs/zakura-pasta-curves/latest/pasta_curves/glv/index.html)
already stores all three rotated x coordinates for joint Eisenstein digits.
This experiment tests a smaller, algebraically compressed storage format in
this codebase. The identity `β²=-1-β` is elementary; the evidence here does
not establish academic novelty or a CPU speedup.
