# Packed x and gauge-class affine layers

The radix-14 four-layer secp256k1 pipeline has two new table/accumulation
variants, both using the frozen 12,288-point uniform-derived fixture with
SHA-256 `a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3`.
The [packed-x overlay](native_packed_x_overlay.py) and
[gauge-layer overlay](native_gauge_layer_overlay.py) are hash-guarded against
the same measured baseline front and window sources, with SHA-256
`3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b`
and `71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d`.
The [frozen Tier 1 manifest](tier1-eisenstein-packed-gauge-cpu40-manifest.json)
and [rules](tier1-eisenstein-packed-gauge-cpu40-rules.json) use the serial
RunPod service, CPU 40, 16 repeats, and adjacent A/A controls. Their
SHA-256 values are `312966d6faaa3b775aef2569764ee24c83f3c7bdaa8828afbc31a5ef7a0e391f`
and `d55c25f23861ac7be80d0119cd9baeb1a991905d5cd9c839a4d0d76139217cf4`,
matching the files on the RunPod instance.

## Methods

The packed entry stores the two signed 128-bit Eisenstein coefficients of
the x coordinate in 33 bytes and a Montgomery y coordinate in 32 bytes.
The selected x unit is obtained by zero, one, or two linear coefficient
rotations and converted to the U256 Montgomery field with the existing
fixed-width bridge. The four-layer affine group operations and exact output
checks are the same as the baseline. The packed table retains **26,384,547
bytes**, compared with **37,192,948 bytes** for the full two-x table.

The gauge-layer path keeps the ordinary 64-byte affine table. It groups
selected leaves by cube-root rotation class, batch-adds each class, rotates
each class sum once, then batch-adds the three sums. The exact algebraic
step is `sum(β^c P_i) = β^c sum(P_i)` for each class `c`; the
[Lean theorem](EisensteinGaugeLayer.lean) checks this redistribution for
one and two applications of an additive rotation. Its hypotheses explicitly
require the rotation to preserve zero and addition. The native path retains
**26,035,988 bytes**. The recoding and curve-operation bridge are checked by
the full point replay below, while the Lean theorem addresses the structural
class-sum step.

## Exact replay and current measurement status

Both x86-64 release candidates compiled and reproduced every point in the
full frozen 12,288-scalar fixture. They verified output points after the
timed interval. The direct diagnostic run recorded **91.921423 ms** for
packed x and **72.134787 ms** for gauge layers, each for 96 consecutive
batches of 128 inputs. These direct times are exploratory.

The serial Tier 1 job `1068b7066ae148de9edfab8aff9075c0` completed all
128 arms and 64 pairs with stable artifacts. The
[independent audit](tier1-eisenstein-packed-gauge-cpu40-audit.json) replayed
both source overlays from the frozen baseline, checked the source and binary
archive, and validated every raw arm. Its predeclared adjacent A/A gate was
`[0.90,1.11]`. The `cal_before` ratio in repetition 9 was **0.8986798**;
the `cal_after` ratio in repetition 10 was **1.1260534**. Both fall outside
the gate, so each aggregate timing result is **unknown after the Tier 1
gate**. Every arm and failed control is retained in the
[raw result](1068b7066ae148de9edfab8aff9075c0/) and its
[archive](1068b7066ae148de9edfab8aff9075c0.tar.gz).

| Same 12,288 scalar stream | Full two-x reference mean | Candidate mean | Descriptive paired reference/candidate median | Aggregate |
| --- | ---: | ---: | ---: | --- |
| Packed x | 64.306887 ms | 94.040668 ms | 0.683206 | Unknown after gate |
| Gauge layers | 64.564821 ms | 71.365855 ms | 0.906319 | Unknown after gate |

The [provenance archive](eisenstein-packed-gauge-native-provenance.tar.gz)
has SHA-256 `f52bf40a35f08d9fdfbe9b269dd3d3783f85ecb75142559304633572f53aa6ae`.
The raw archive has SHA-256
`b1d639fa23cb40dd802a9a727da6919bf1f1c62abd5c33112d8ab7b4b5099e3a`.

| Variant | Front SHA-256 | Window SHA-256 | Binary SHA-256 |
| --- | --- | --- | --- |
| Packed x | `2b26dc2b5ddcf06800e3dd7109d6e167306bdfa4743dc63ef6f29fa185016df3` | `7b7f6eff42dc9e7197b8c6c30d3792ebc18e6f17443e8944fc5fe0d3452117ca` | `60f282f5ce2b730440bb8ab0ca747ea1184dd2405b448ad8971a1d03362dfd31` |
| Gauge layer | `5ef632cd74ea7bc3ec38ce7b815481bf91cd56e8d2444621e1d010a95ea8edee` | `3650b42e1ff33c761efd7fd73a3dac4c12a21111afe5fbc8ac73b4e0782557bd` | `f0a60937e9af8efae3b3572929be51f411d1d56bb53dee97ef0a0d8b17593874` |

The environment is a cloud-instance Tier 1 pod. Its container reports one
NUMA node and CPU affinity, while physical-host exclusivity is unverified.
