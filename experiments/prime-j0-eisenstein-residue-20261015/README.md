# A 33-byte Eisenstein residue x coordinate

The secp256k1 prime splits in the Eisenstein integers. An exact norm-
`p` element

`π = -367917413016453100223835821029139468249
     -64502973549206556628585045361533709078·ω`

defines `F_p ≅ Z[ω]/(π)`, where `ω²+ω+1=0`. Map a pair `(u,v)` to
`u+vβ mod p`, with
`β=0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee`.
The exact computations give `N(π)=p`, `π(β)=0 mod p`, and
`β²+β+1=0 mod p`. The map is onto because integer pairs `(u,0)` reach every
residue. The ideal `(π)` has index `N(π)=p`, so it equals the map's kernel.
This supplies a two-coordinate field representation with order-three
rotation

`ω·(u+vω) = -v + (u-v)ω`.

Rotation uses integer additions and subtraction, with no 256-bit constant
field multiplication. General multiplication uses three approximately
129-bit products: for `A=us`, `B=vt`, and `C=(u+v)(s+t)`, the unreduced
product is `(A-B, C-A-2B)`. The
[exact prototype](eisenstein_residue.py) subtracts rounded multiples of the
ideal basis `π=(a,b)` and `ωπ=(-b,a-b)`; their determinant is `p`, so this
reduction preserves the field residue. Its current Python reduction uses
exact large-integer division. The native cost of that division and the
field-to-coordinate conversion must be measured before routing scalar
multiplication through this format.

Rounding the inverse-basis coordinates puts each error in `[-1/2,1/2]`.
Consequently, the reduced first coordinate has magnitude at most
`(|a|+|b|)/2`, and the second at most `(|b|+|a-b|)/2`. Both sums are strictly
below `2^129`, so each magnitude is below `2^128`. Two sign-and-128-bit-
magnitude coordinates pack into **258 bits, or 33 bytes**. Coupled with a
32-byte affine y coordinate, the packed point payload is **65 bytes**;
the current two-x table entry is 96 bytes. A plain pair of signed 128-bit
integers is insufficient: 1,984 of 20,000 reduced pairs examined by
the 10,000-case check had at least one coordinate outside its signed range.
The prototype performs actual 33-byte pack/unpack round trips.

The [10,000-pair receipt](self-check-10000.json) checks conversion,
addition, one and two rotations, multiplication, reduction idempotence,
and pack/unpack against ordinary `F_p` arithmetic. Every comparison passed;
the maximum observed absolute coordinate length was 128 bits. The
[1,000-pair receipt](self-check.json) is a smaller bounded screen.
These are exact correctness screens. The conversion-free
[native field and curve kernel](eisenstein_pair_native.rs) implements pair
addition, subtraction, rotation, three-product multiplication, 33-byte
pack/unpack, Jacobian doubling, mixed addition, and binary scalar
multiplication. The source SHA-256 is
`b47b200bbbca7c731bff22854f37967d7cda8e9ba9b37db58ce6c7969905dcf6`;
the x86-64 Linux release binary SHA-256 is
`bdd612d844c40852f32742601ca02d9c0cd73837d72f08da9b0fa5b87072a543`.
On RunPod it verified every result from the frozen 12,288-scalar fixture by
comparing projective coordinates against independently computed affine
points, and round-tripped both packed affine coordinates for every case.
The full replay recorded `54,846.381069 ms` for the Solinas-reduced binary
scalar stream. This full replay is a correctness and implementation-cost
diagnostic; the separate paired CPU panel below supplies its timing gate.

The field reducer originally used two arbitrary-precision divisions per
operation. For `p=2^256-c`, `c=2^32+977`, let `q₀` be the arithmetic
256-bit shift of the centered numerator and `low` its nonnegative low
256 bits. The exact remainder relative to `p` is `low+q₀c`. When
`|q₀c|<p-c`, this remainder lies in `(-p,2p)`, so one branch correction
produces the exact quotient. The native kernel retains both the division
and this shift-and-correction path in one executable. The frozen
[Tier 1 panel](tier1-eisenstein-reducer-cpu40-manifest.json) pairs them on
the first 128 unique scalars of the same fixture, with 16 alternating
repetitions and adjacent A/A gates from the
[predeclared rules](tier1-eisenstein-reducer-cpu40-rules.json). Its RunPod
job is `16ad0015d96b497ca15cc3de3ce090e6`.

The completed [panel](16ad0015d96b497ca15cc3de3ce090e6/summary.json)
contains 96 valid arms and all 48 planned pairs, with stable artifacts.
Every adjacent A/A ratio passed `[0.90,1.11]`. The
[audit](tier1-eisenstein-reducer-cpu40-audit.json) matched every raw output,
stderr file, source/binary/fixture hash, case order, and pair to the
manifest; it also checked the full correctness replay in the
[provenance archive](eisenstein-pair-native-provenance.tar.gz). The raw
[result archive](16ad0015d96b497ca15cc3de3ce090e6.tar.gz) has SHA-256
`8f348881ae400a0e14eefc960935afab08f7520ee82361af8464587f3383c0c7`;
the provenance archive has SHA-256
`9f963999a6d43ab489ac872f118ed218ba355d8ea20519aac7a36e03bf1ddce7`.

| Tier 1 same-input binary scalar stream, 128 outputs | General division | Solinas shift and correction |
| --- | ---: | ---: |
| Mean timed multiplication | 593.263493 ms | 572.856894 ms |
| Mean time per scalar | 4.634871 ms | 4.475445 ms |

The median paired division/Solinas ratio is **1.037568×** across 16
comparison pairs, with a predeclared paired bootstrap 95% interval of
`[1.028125,1.046558]`. The result qualifies the reducer change for this
BigInt pair-field binary multiplier on the observed Tier 1 cloud instance.
The measured scope is the 128-scalar binary multiplier. The existing
radix-14 four-layer pipeline uses fixed-width field arithmetic; this
prototype's hundreds of milliseconds per 128 scalars identify
arbitrary-precision allocation and reduction as the next cost center to
remove before integrating the pair format.

The [bounded-limb native kernel](eisenstein_pair_fixed.rs) stores pair-field
intermediates in signed stack-allocated 512-bit words, uses the exact
shift-and-correction reducer above, and delays lattice reduction across
linear field operations. Its [limb arithmetic](eisenstein_pair_fixed_int.rs)
passed 20,000 deterministic differential cases against BigInt for signed
addition, subtraction, multiplication, shifts, and arithmetic right shift.
The kernel reproduced all 12,288 fixture points and checked packed-coordinate
round trips and rotation on each expected point; its full-stream diagnostic
was `16,588.936079 ms`. Source SHA-256 values are
`3ea92f86325393a82a22f904c989cadb47b17d1a56662c68d75c9d320e79ab74`
for the scalar front and
`25537aabf5910413d147c0ced07b5e693226d4e239586ab51571bb3dc6a6a7aa`
for limb arithmetic; the release executable SHA-256 is
`39c8c126562ff2e388c7ab2c86b8d19cbb8bbe761d02509ec02a2cd4d0a6e704`.

The next frozen [Tier 1 panel](tier1-eisenstein-fixed-cpu40-manifest.json)
paired this kernel with the BigInt Solinas path on the same first 128
scalars, with 16 alternating repetitions and adjacent A/A controls. Its
[independent audit](tier1-eisenstein-fixed-cpu40-audit.json) checked all
96 valid arms, 48 valid pairs, stable hashes, raw outputs, differential
test, and full-stream replay. One A/A ratio in repetition 8 was
`1.1139876338286885`, above the frozen `[0.90,1.11]` acceptance range.
The aggregate status is therefore **unknown after the Tier 1 gate**.

| Same-input 128-scalar BigInt/fixed panel | BigInt Solinas | Bounded limbs |
| --- | ---: | ---: |
| Descriptive mean timed stream | 563.768475 ms | 174.937160 ms |

The descriptive median paired ratio was `3.238713×`, with bootstrap 95%
interval `[3.220723,3.245879]`; these values retain the failed A/A pair
and are diagnostics. The [raw panel archive](c325c7ff36a74f0c8cd85db3024432f8.tar.gz)
has SHA-256 `93271f906b9c43ed5bf7f6588ca70a7132e22078b4c5be5e05bdeaed0245d8b5`;
the [provenance archive](eisenstein-pair-fixed-provenance.tar.gz) has SHA-256
`9565e05ca05170a79e0d6fdcae7651348059f91288a8b64e2c41776b10688d3e`.

## Radix-128 Montgomery reduction in the quotient field

The [exact prototype](eisenstein_montgomery.py) changes how a pair-field
product is reduced. Write `R=2^128`, `π=(a,b)`, and let `(x,y)` be the raw
three-product result. Since `π·conj(π)=p`, the adjugate numerators are

`N₁=(a-b)x+by` and `N₂=-bx+ay`.

With `s=p⁻¹ mod R`, choose centered 128-bit coefficients
`q₁=-sN₁ mod R` and `q₂=-sN₂ mod R`. The coordinates
`x+q₁a-q₂b` and `y+q₁b+q₂(a-b)` are both divisible by `R`; dividing
them by `R` gives the Montgomery product modulo `π`. The
[native scalar path](eisenstein_pair_montgomery.rs) derives each quotient
from low 128-bit products, computes the exact divided pair, and applies
the prior canonical lattice reducer only when the output exceeds its
128-bit coordinate bound. Encoded field inputs are `xR mod p`.

The [10,000-pair receipt](montgomery-self-check-10000.json) verifies
encoding, decoding, exact divisibility, product, rotation, and coordinate
bounds. The largest observed intermediate coordinate and Montgomery
quotient occupied 128 and 127 bits, respectively; the subsequent canonical
quotients occupied at most one bit. Canonical correction changed 1,818
of the 10,000 product pairs. These are observed bounds for that screen.
The native path reproduced all 12,288 frozen scalar points, with a
full-stream diagnostic of `14,211.422772 ms`. Its source SHA-256 is
`b112265e746cc91adbb09cd954f1c7008fbbd7e2ee35a403606c40d4c6dac1dd`;
its x86-64 release executable SHA-256 is
`7501334a41f324ac92e7243c0feca5bdf5de2caf3a58c5cbd19049018983c94c`.

The frozen [Tier 1 manifest](tier1-eisenstein-montgomery-cpu40-manifest.json)
and [acceptance rules](tier1-eisenstein-montgomery-cpu40-rules.json) pair
the fixed-limb Solinas and Montgomery kernels on 512 common scalars in
16 alternating repetitions, with adjacent A/A controls on CPU 40. The
serial RunPod job is `273359b6d2724700ad59ea1ddc978da8`.
The completed [panel](273359b6d2724700ad59ea1ddc978da8/summary.json)
contains all 96 valid arms and 48 valid pairs with stable source and binary
artifacts. Every A/A ratio passed its frozen `[0.90,1.11]` gate. The
[independent audit](tier1-eisenstein-montgomery-cpu40-audit.json) checked
every raw output and pair, regenerated the 10,000-pair exact screen, and
matched the full native replay and source hashes in the
[provenance archive](eisenstein-montgomery-native-provenance.tar.gz).

| Tier 1 same-input binary scalar stream, 512 outputs | Fixed-limb Solinas | Radix-128 Montgomery |
| --- | ---: | ---: |
| Mean timed multiplication | 726.038362 ms | 605.537759 ms |
| Mean time per scalar | 1.418044 ms | 1.182691 ms |

The median paired fixed/Montgomery ratio is **1.200722×** across 16
comparison pairs; the predeclared paired bootstrap 95% interval is
`[1.187866,1.207221]`. The qualified scope is this conversion-free
binary scalar path on the observed Tier 1 cloud instance. The timed
interval starts after fixture loading and generator conversion, includes
scalar parsing and projective arithmetic, and ends before exact point,
rotation, and pack/unpack checks. The [raw archive](273359b6d2724700ad59ea1ddc978da8.tar.gz)
has SHA-256 `2d8f889cd7ecfe2d2532b2c672bf6d51ec368ddf2002a95570fb64c90f91bc1b`;
the provenance archive has SHA-256
`a59b84ac34fb3e98df29b8714fd3c0b5cb3b6e74acae32655587472bfbdfcf88`.

## Proof map

The pinned Lean 4.34.1 module
[EisensteinResidue.lean](EisensteinResidue.lean) was built with
`lean EisensteinResidue.lean`; the [output](lean-check.log) records
`#print axioms` for each declaration. The same toolchain checked
[EisensteinMontgomery.lean](EisensteinMontgomery.lean) with
`lean EisensteinMontgomery.lean`; its [output](eisenstein-montgomery-lean-check.log)
records the additional declarations. The same toolchain checked
[EisensteinGaugeLayer.lean](EisensteinGaugeLayer.lean) with
`lean EisensteinGaugeLayer.lean`; its
[output](eisenstein-gauge-layer-lean-check.log) records both class-sum
declarations.

| Result | Lean declaration | Status |
| --- | --- | --- |
| Three successive coordinate rotations return the pair | `rotate_three` | Checked; Lean foundations `propext`, `Classical.choice`, `Quot.sound` |
| `N(π)=p` | `pi_norm_eq_prime` | Checked; no axioms |
| `β²+β+1=0 mod p` | `beta_cubic` | Checked; no axioms |
| `π(β)=0 mod p` | `pi_in_kernel` | Checked; no axioms |
| Both ideal-basis widths are below `2^129` | `basis_x_width`, `basis_y_width` | Checked; no axioms |
| Pair-coordinate rotation preserves the field map modulo `p` | `eval_rotate_mod` | Checked; Lean foundations `propext`, `Quot.sound` |
| Three-product pair multiplication preserves the field map modulo `p` | `eval_mul_mod` | Checked; Lean foundations `propext`, `Quot.sound` |
| One exact quotient correction for a pseudo-Mersenne prime under the asserted correction bound | `solinas_one_correction` | Checked; Lean foundations `propext`, `Classical.choice`, `Quot.sound` |
| Eisenstein adjugate identities | `adjugate_x`, `adjugate_y` | Checked; Lean foundations `propext`, `Quot.sound` |
| Modular inverse and quotient congruences give integer witnesses | `inverse_mod_witness`, `quotient_mod_witness` | Checked; Lean foundations `propext`, `Quot.sound` |
| Both Montgomery numerator coordinates are divisible by the radix under the inverse and quotient congruence hypotheses | `montgomery_numerators_divisible` | Checked; Lean foundations `propext`, `Quot.sound` |
| Direct radix-congruence form of numerator divisibility | `montgomery_divisible_from_congruences`, `secp_montgomery_divisible` | Checked; Lean foundations `propext`, `Quot.sound` |
| The divided pair has the intended field residue | `montgomery_field_semantics` | Checked; Lean foundations `propext`, `Quot.sound` |
| An additive rotation commutes with class sums, including two successive rotations | `EisensteinGaugeLayer.rotate_list_sum`, `rotate_twice_list_sum` | Checked in [EisensteinGaugeLayer.lean](EisensteinGaugeLayer.lean); first theorem has no axioms, second uses `propext` |
| Numeric inverse, norm, and kernel conditions for secp256k1 | `prime_inverse_radix`, `norm_pi`, `pi_kernel`, `omega_pi_kernel` | Checked; no axioms |
| Full quotient-ring isomorphism, multiplication preservation, and rounding bounds | — | Formalization partial; a concrete `Z[ω]` quotient-ring definition and the map's kernel/index bridge remain open |
| Bit-level Rust signed-limb operations and the centered quotient implementation | — | Formalization partial; 20,000-case differential limb replay, exact Python screen, and full native point replay are the current executable checks |

The binary paths establish arithmetic correctness and expose field cost.
The integrated comparison charges point selection, field operations, and
affine recovery on the same frozen fixture under the Tier 1 gates.

The [packed-x and gauge-layer follow-up](PACKED_GAUGE.md) now implements
two radix-14 variants on that fixture. Both passed all 12,288 point checks.
The serial Tier 1 panel completed 128 arms with stable artifacts; two
adjacent A/A controls missed their frozen bounds, so both aggregate timing
comparisons remain unknown after the Tier 1 gate. The follow-up records
the exact memory costs, descriptive timings, proofs, and raw receipts.

The [projective class-join follow-up](GAUGE_PROJECTIVE.md) keeps the same
gauge table and replaces the final affine layer with two XYZZ mixed joins
and one batch inversion. It reproduced all frozen points. Its 96-arm serial
Tier 1 panel passed every A/A gate and measured a qualified paired
reference/projective ratio of `0.983894` with 95% interval
`[0.974294,0.988284]`, directing further work away from that join.

The [rotation-cache follow-up](ROTATION_CACHE.md) places two-x precomputation
in ten of fourteen radix-14 digit rows within the 32 MiB table cap and
replays 12,288 scalar points exactly. An independent 20,000-scalar training
profile found that per-seed hot entries do not transfer to the held-out
fixture, so the ten-row mask uses evenly spaced rows. Its serial Tier 1
panel completed all 96 arms, but two A/A controls exceeded the frozen
range; the timing aggregate remains unknown with all raw receipts retained.

The [norm-110557 alternate radix](ALT_RADIX.md) uses fifteen full two-x
digit rows and a small terminal set, retaining 27,429,548 bytes under the
32 MiB cap. It replayed all 12,288 frozen points. Lean checks its quotient
identity, prime norm, norm scaling, and a conditional terminal recurrence.
Its serial Tier 1 panel completed 96 arms; one A/A control missed the frozen
range, and the paired interval crossed one, so the aggregate speed comparison
remains unknown.

The [balanced-pair accumulation screen](PAIR_ACCUMULATION.md) keeps selected
points in Eisenstein coordinates throughout the group sum and also replayed
all frozen points. Its 1,036.845373 ms full-stream diagnostic versus roughly
64–68 ms for the ordinary-field cached paths falsifies direct pair-field
accumulation as the next timing candidate; its source, binary, and receipt
remain archived.

The [hybrid reduction screen](HYBRID_TREE.md) moves the final one or two
affine tree layers to XYZZ joins and batch-normalizes outputs. Both variants
replayed 12,288 points with the same norm-110557 table; their diagnostics
were close to the all-affine path and are retained as stage evidence.
