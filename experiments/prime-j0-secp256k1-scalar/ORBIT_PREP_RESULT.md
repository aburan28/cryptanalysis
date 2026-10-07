# Prepared unit orbit on fresh 256-bit inputs

The protocol and evaluator were frozen in `f4f68786` before deriving
the new inputs. The checked Sage launcher reported `status: verified`,
Sage `10.10.rc0`, accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and runtime receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The input digest is
`41b32902d1f85a49641d98eb7adee40934a2d215b23619c372d3e2abb94e9ea0`.
The raw 128 paired cases, exact inputs, source hashes, and preparation
digests are in `orbit-prep-result.json`.

All 128 secp256k1 outputs matched Sage's independent `kP` in both
arms. They used identical width-four digits, τ positions, paired
strides, and mixed additions. The prepared-orbit arm made every paired
Z scale a negation and selected every digit from its prepared orbit
without a field multiplication.

| Frozen generic-path count, 128 scalars | On-demand rotation | Prepared orbit |
| --- | ---: | ---: |
| τ positions | 20,356 | 20,356 |
| Paired strides | 9,595 | 9,595 |
| Cheap Z scales | 7,470 | 9,595 |
| Mixed-add calls | 4,652 | 4,652 |
| Digit/final rotations | 96 | 0 |
| Evaluator `M` | 100,647 | 98,426 |
| Evaluator `S` | 54,284 | 54,284 |
| Evaluator `M+S` under `S=M` | 154,931 | 152,710 |

The prepared orbit saves **2,221 nominal multiplications** during
evaluation. Building the three X-coordinate versions of each of nine
already-affine seed points costs exactly **9M per base**, or 72M for
the eight bases in this panel. Including that orbit work, the panel's
incremental count is 152,782 versus 154,931, saving **2,149 units
(1.387%)**. If each scalar instead had its own freshly prepared base,
the same nine extra orbit multiplications would be charged to it;
every one of the 128 per-scalar evaluator savings was between 11 and
26, so the incremental net saving was between 2 and 17 units per
scalar. This comparison holds the nine affine seed points fixed; their
construction and normalization remain unknown and uncharged in both
arms.

The orbit requires 27 affine point representations instead of nine.
Lookup and memory costs, exceptional paths, recoding, inversion,
normalization, and program overhead are not in the generic-path
count. No CPU time or host-isolation receipt was produced;
`cpu_speedup_claim` is `null`.

This reproduces a published idea: [Xu, Yu, Han, and Lu](https://eprint.iacr.org/2024/1906),
Section 4.2, explicitly charge nine field multiplications to prepare
the `ω` images of their nine seed points and obtain `ω²` images by
subtraction. The prepared-orbit arm is therefore a stronger **prior-art
control**, not a new scalar-multiplication scheme. It supersedes the
on-demand width-four arm as the relevant published-method stage
baseline. A competitive or novel result still requires complete
preparation and native single-scalar comparison.
