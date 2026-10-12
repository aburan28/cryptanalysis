# One-use inversionless projective τ seed table

The comparison source and protocol were frozen in `deae772e` before
deriving 64 fresh secp256k1 one-use base/scalar pairs. The repository's
checked Sage launcher returned `status: verified`; the saved
`projective-endo-runtime-info.json` receipt has SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The input digest is
`5721b376437af82f40f82926c98eba0a04cf7edff87f1295edc1375799e5ed7e`.
The raw inputs, exact source counts, point digests, and outputs are in
`projective-endo-result.json`.

Both arms used the optimized nine-seed endomorphism chain, identical
width-four digits and unit-orbit choices, and the same paired-τ schedule.
One retained constructed seeds in Jacobian coordinates; the other
batch-normalized eight constructed seeds. Every seed matched its stated
`aP+bτP` value and both complete scalar outputs matched Sage on all 64
cases.

| 64 one-use scalars; generic source counts | Keep projective | Normalize eight |
| --- | ---: | ---: |
| Preparation `M`, `S`, inversions | 3,264; 2,048; **0** | 6,144; 2,560; **64** |
| Online `M`, `S` | 57,182; 29,126 | 49,110; 27,108 |
| General / mixed online additions | 2,018 / 236 | 0 / 2,254 |
| Complete `M+S`, inversion separate | 91,620 | 84,922 |

The projective arm pays an additional 6,698 `M+S` across the panel,
or **104.66 per scalar**, to avoid one *preparation* inversion per scalar.
The per-case threshold ranges from 87 to 122 `M+S`. Broken out by
operation, projective costs an extra 67–95 multiplications and 20–27
squarings per case. These are not wall-time measurements. The common
final output inversion and independently checked scalar replay are
outside the table and cancel in the paired difference.

In the repository's current Rust `SecpFieldElement::inv`, each of 256
iterations performs one field multiplication and two squarings, for a
fixed **256M+512S** source count before moves and loop overhead.
Therefore, *if these Jacobian paths used that same field kernel and
inverse*, the projective arm would use fewer multiplications and fewer
squarings on every tested case. This is an inference from the Rust
source, not a measured native scalar run; the Rust point implementation
currently uses different projective formulas. A future faster inverse
could change the representation choice.

Both projective precomputation and cached readdition are established
techniques: see the [Explicit-Formulas Database](https://www.hyperelliptic.org/EFD/g1p/index.html)
and [high-speed ECC work using projective precomputed points](https://eprint.iacr.org/2010/315.pdf).
The `τ` width-four control is [Xu et al.](https://eprint.iacr.org/2024/1906).
No academic novelty or controlled CPU speedup is claimed. The next
experiment caches each projective seed's `Z²` and `Z³` once across its
unit-orbit uses, charging the cache construction and every readdition.
