# Scalar-conditioned normalization on fresh secp256k1 inputs

The protocol and source were frozen in `9b62931d` before the fresh
64-case input set was derived. The checked Sage launcher reported
`status: verified`, Sage `10.10.rc0`, accepted runtime manifest
SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The input digest is
`c5d51a3bcb7ffcf8ac06efc42e673c617de06ab9e5c66cfac2b8bc193dcc6332`.
The raw per-case base, scalar, selected seed indices, point digests,
costs, source hashes, and correctness are in `selective-result.json`.

For every fresh base, the explicit Jacobian chain constructed all nine
seed points and checked them against Sage. The zero-normalization,
frequency-selected, and all-affine representations each recovered the
same independently checked `kP` on all **64 scalars**. They used the
same width-four digits and paired-τ schedule. The selective rule
normalized a constructed seed if it appeared at least twice after the
free first insertion. It selected six points in eight cases, seven
in 27, and all eight in 29 cases.

| One-use arithmetic over 64 scalars | Keep projective | Selective | All affine |
| --- | ---: | ---: | ---: |
| Normalized constructed points | 0 | 469 | 512 |
| Mixed additions | 264 | 2,191 | 2,227 |
| General Jacobian additions | 1,963 | 36 | 0 |
| `M+S`, excluding inversion | 91,590 | 85,046 | 85,167 |
| Field inversions | 0 | 64 | 64 |

Selective normalization saves **121 `M+S` units** over normalizing
all eight points across the panel, with the same 64 inversions. It
improves 35 cases and ties 29; the mean saving is only **1.89 units
per scalar**. The policy is therefore **not promoted** as a new
scalar-multiplication scheme.

Compared with keeping all points projective, selective normalization
saves 6,544 `M+S` units but requires 64 inversions. Its aggregate
break-even price is **102.25 `M+S` units per inversion**. Individual
case thresholds range from 79 to 136. Full normalization breaks even
at 100.36 units per inversion on this input set. The actual price of
inversion depends on the native field implementation, so neither
representation has a verified CPU advantage. Recoding, lookup,
memory traffic, exceptional paths, and runtime overhead are outside
the arithmetic model; `cpu_speedup_claim` is `null`.

The [width-four digit/orbit method](https://eprint.iacr.org/2024/1906)
and [Montgomery batch inversion in ECC precomputation](https://globals.ieice.org/en_transactions/fundamentals/10.1587/e86-a_1_98/_p)
have prior art. This experiment tests a scalar-conditioned subset
policy within those techniques; its academic novelty is unproved and
its measured formula advantage is too small to be a compelling lead.
The next gate is native inversion calibration and a full one-use
scalar comparison before choosing projective or affine table points.
