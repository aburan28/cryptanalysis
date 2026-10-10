# Fourteen-window mixed-radix tau atlas

This candidate uses six radix-512 and eight radix-640 windows with the
existing two-bucket tau identity and grouped-unit gauge. The exact
[coverage and termination proof](PROOF.md) gives **415,190 affine seed
points**, a 26,572,160-byte point payload, and 4,729,980 bytes of binary
atlases. The new full and final radix-640 atlases decode all 409,600
residues and satisfy their declared norm bounds.

Source and atlases were frozen at `0c346ac93a7d87f757f7f9917f2bc95213a2c614`
before drawing 4,096 disjoint scalars with seed `20261010158` and scalar
digest `4d2443d34df7b240b1c53f7d935e2608163acdee4c76a9eef1d8e37eff9d712c`.
The independent affine replay checked exact integer reconstruction,
per-term bucket evaluation, grouped-gauge evaluation, and binary scalar
multiplication for every scalar. All 4,096 passed. A 64-scalar design
replay had passed before the freeze.

| Paired point-kernel measure, 4,096 scalars | Mixed radix 640 | Fifteen-window gauge |
| --- | ---: | ---: |
| Mixed additions | **53,248** | 57,344 |
| Grouped Solinas rotations | **15,094** | 15,351 |
| Stored affine points | 415,190 | 233,423 |
| Point payload bytes | 26,572,160 | 14,939,072 |

The format saves 4,096 mixed additions and 257 Solinas rotations on the
paired panel. Applying the frozen source-loop model of 8 generic
multiplies plus 2 squares per mixed addition, 36 limb products per
generic field operation, and 23 per Solinas rotation gives **1,480,471
fewer point-kernel limb products**. This model excludes the extra
radix-640 integer division, table construction, and all host timing.
`verify.py` checks the source freeze, disjoint inputs, group replay
receipt, binary atlas hashes, same-input control counts, and the
[exact radix-640 quotient routine](FAST_DIVISION.md). That routine
replaces generic long division by two constant divisions by five for
each nonbinary coordinate update; it passed 100,000 deterministic
129-bit inputs and signed boundary cases.

The shared native evaluator source is reserved by an earlier Conductor
task. Native operation accounting and controlled CPU timing are subsequent
gates. The current RunPod Pod does not pass the host-level isolation
preflight in [the benchmark protocol](../../docs/ISOLATED_BENCHMARKS.md).
