# Cached projective τ digit table for one-use secp256k1 scalars

The cached-projective protocol and source were frozen in `55baf12b`
before generating 64 fresh one-use base/scalar pairs. The checked Sage
launcher returned `status: verified`; the saved runtime receipt has
SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The input digest is
`4a563c0aa3d001cd8809df6b2388e3c4ea99404026d91b51ac64d00cba399310`.
`cached-projective-result.json` contains every input, prepared seed and
orbit digest, source count, and checked scalar output.

Both arms used the same endomorphism-assisted nine-point Jacobian
chain, width-four digits, and paired-τ schedule. The candidate cached
each projective seed's `Z²` and `Z³` once if the seed appeared in a
general addition. The seed's three unit-orbit images have the same
`Z`, so one cache entry serves all three. Every seed point matched its
declared `aP+bτP` value, and all **128 complete arm outputs** matched
Sage on the 64 fresh cases.

| 64 one-use scalars; source counts | Projective uncached | Projective cached |
| --- | ---: | ---: |
| General additions | 2,001 | 2,001 |
| Distinct charged `Z²,Z³` cache entries | 0 | 508 |
| Complete `M+S`, no preparation inversion | 91,642 | **88,656** |

One cache entry costs `1M+1S`; one cached general addition saves
`1M+1S`. The net saving is therefore `(2,001−508)=1,493`
multiplications **and** 1,493 squarings, or **46.66 `M+S` per scalar**.
No inversion was performed during projective seed preparation. The
common final affine-output inversion is excluded from both arms.

## Paired all-affine control

The affine replay source and protocol were frozen in `2cf0a927`
before running on the **same saved 64 cases**. It independently rebuilt
and verified all nine optimized seeds, batch-normalized the eight
constructed seeds with one inversion, and checked every scalar output
against Sage and the frozen point. It is a paired control on an already
observed panel, not a separate fresh panel. Full counts are in
`cached-affine-replay-result.json` (SHA-256
`98ea45f7633c4c4e8ac95abfe8cde44f57e434d67969f2e83a4f6efbd4e29f71`).

| Complete generic source count, 64 scalars | Cached projective | All affine |
| --- | ---: | ---: |
| Field multiplications | 58,965 | 55,334 |
| Field squarings | 29,691 | 29,695 |
| Preparation inversions | **0** | 64 |
| `M+S` excluding inversions | 88,656 | 85,029 |

The cached projective arm requires **3,631 more multiplications but
four fewer squarings** across the panel, while avoiding 64 preparation
inversions. Its paired break-even inversion price is **56.67 `M+S`
per scalar**, with case thresholds from **41 to 71**. On each case it
uses 41–71 more multiplications and zero or one fewer squaring. The
common output inversion cancels and is not included in either count.

The repository's current Rust `SecpFieldElement::inv` executes a
256-round ladder containing `256M+512S`. If this Jacobian path is
implemented with that field routine, its source field-operation
count beats all-affine on every tested case. This is an inference
from source code and the verified point-operation schedule. The
existing Rust point implementation uses different formulas; no
native complete scalar timing has been run. Even a source-count
advantage does not prove a CPU wall-time advantage under cache,
branch, lookup, allocation, and recoder costs.

The underlying [width-four τ method](https://eprint.iacr.org/2024/1906),
[projective precomputation](https://eprint.iacr.org/2010/315.pdf), and
[cached `Z²,Z³` readdition](https://www.hyperelliptic.org/EFD/g1p/index.html)
all have prior art. This specific composition is an implementation
candidate, **not an established novel method**. `cpu_speedup_claim` and
`academic_novelty_claim` remain `null`. The next gate is a native
one-use 256-bit implementation and full-operation timing on an
isolated host, paired with strong published baselines.
