# ARM64 carryless field kernel for the N131 four-atom inverse

Replacing the bit-serial `GF(2^131)` product in the exact W15
four-atom inverse with ARM64 `PMULL`, then adding a byte-table squaring
map, preserves **all 16,384 first-product decisions** on both frozen
N131 fixed-output controls. The positive case retains the same single
algebraic product root and the independent field control retains zero.
The final kernel's observed query intervals were **1.888 s** and
**2.039 s**, compared with **6.522 s** and **6.964 s** in the archived
native run. These are exploratory stage observations on an unisolated
host; they do not establish a controlled CPU speedup or a complete IC
online interval.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is
the frozen W15 mask-XOR seed `13686` at Frobenius rotations `(26,39)`.
Both inputs, the original degree-eight resultant, the source-product
spaces, the output serializer, and the native algorithm remain those of
the [archived inverse](../n131_w15_rotated_fouratom_inverse_20261010/RESULT.md).
Only field multiplication and squaring for degree 131 change. The N41
path retains the archived operations; non-ARM builds select the portable
bit-serial multiplier.

The [carryless kernel](field_fast.hpp) multiplies three 64-bit limbs
using nine ARM64 polynomial products and reduces twice by
`t^131=t^13+t²+t+1`. The second fold has at most 12 bits. The
[square-table generator](generate_fast_sq.py) adds a 17-byte lookup
decomposition of the linear squaring map. The frozen source-copy
[generator](generate_fast.py) changes only the N131 multiplication call
in the original C++ inverse; the generated
[first](native_fast.cpp) and [second](native_fast_sq.cpp) variants are
archived with their binaries. The first variant isolates the product
change, and the second adds the squaring map.

| Fixed-output N131 query stage, one native worker | Archived bit-serial | PMULL | PMULL + byte-table square |
| --- | ---: | ---: | ---: |
| Positive, one algebraic product root | 6.522 s | 3.307 s | **1.888 s** |
| Independent field control, zero roots | 6.964 s | 3.361 s | **2.039 s** |
| First-product states visited | 16,384 | 16,384 | 16,384 |
| Exact serialized semantic output | Reference | Identical | Identical |

The [first](protocol.json) and [second](protocol_v2.json) protocols froze
source and input hashes, Apple clang 17 `-O3 -std=c++17`, ARM64, one
worker, 100-second native query cap, and 4-GiB RSS cap before their
respective builds and runs. The [field test](test_field.cpp) compared
**10,036 products** against the archived multiplier, including field
extrema and deterministic random operands. It passed both with ARM64
`PMULL` and with `__ARM_FEATURE_CRYPTO` disabled at compile time.
The [independent audit](audit_result.json) checks every semantic field
of the positive and control outputs against the archived JSON, including
the recovered GCD root; it retains source, binary, protocol, and output
hashes. The native peak RSS stayed below 2.4 MiB in these controls.

Recompiling the final source from the repository produced a different
macOS binary hash, but its positive output matched the measured final
binary in every semantic field. The rebuilt binary and
[replay output](positive_rebuilt.json) are retained; the audit records
both binary hashes. Its separate 1.289-second exploratory query interval
illustrates the host timing variation, and is not substituted for the
frozen comparison row above.

The fast kernel reduces the cost of checking one **proposed** block
output. The remaining algorithmic gate is target-conditioned generation
of a small set of compatible outputs while multiple source seeds and
pair blocks remain free. Test that generator on the unpinned N41 public
point with group and column replay, then project its complete N131 work
and memory within one worker, 600 seconds, and 4 GiB before an ordinary
challenge-width query. Relation yield, novel rank, factor logs, fresh
target recovery, and matched same-point rho timing remain later pipeline
measurements. This kernel experiment has `candidate_id: null`.
