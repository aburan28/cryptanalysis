# Fresh 256-bit sparse-digit control

The protocol and evaluator were frozen in `3a041a07` before the
SHA-256-labeled inputs were derived. The checked Sage launcher returned
`status: verified`, Sage `10.10.rc0`, accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and runtime receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The fresh input digest is
`fceb379d7a38a0983d7682a103e06c06fd407b19ac59415927a5a32e63dd3603`.
The raw per-case rows, exact base/scalar inputs, source hashes, and
prepared-point digests are in `width4-result.json`.

All 128 scalar outputs, across eight bases and sixteen scalars per
base, matched Sage's independent `kP` in all three arms. The sparse
width-four stream reconstructed exactly the same short `(a,b)` pair
used by the dense stream. Its mean weight was **36.27** nonzero digits,
versus **105.66** for dense unit digits. Mean lengths were 159.75 and
159.52 positions, respectively. The two width-four evaluators used
identical digit streams, τ positions, and mixed-add counts.

| Frozen generic-path count over 128 scalars | Dense paired | Width-four Horner | Width-four paired |
| --- | ---: | ---: | ---: |
| τ positions | 20,290 | 20,320 | 20,320 |
| Mixed-add calls, including free first call | 13,524 | 4,642 | 4,642 |
| Paired strides | 5,133 | 0 | 9,577 |
| Cheap Z scales | 3,418 | 0 | 7,344 |
| Digit/final rotations | 104 | 3,138 | 93 |
| Field multiplications `M` | 179,881 | 120,530 | 100,564 |
| Field squarings `S` | 80,768 | 54,182 | 54,182 |
| `M+S` under `S=M` | 260,649 | 174,712 | 154,746 |

The sparse paired arm used **105,903 fewer `M+S` units (40.63%)** than
the dense paired arm on these matched inputs. It used **19,966 fewer
units (11.43%)** than the sparse Horner arm. Every individual scalar
had a positive count difference in both comparisons. These are
source-formula differences, not CPU speedups. The sparse method is
based on the [published width-four digit set and tripling
approach](https://eprint.iacr.org/2024/1906); the result is a 256-bit
control and correctness check, not an academic novelty claim.

Each base's nine affine seed points were prepared with Sage group
operations outside the evaluator. The eight preparation digests are
saved, but their arithmetic cost is **unknown**, and sixteen scalars
share each preparation. No single-use variable-base, full-operation,
or cold-start cost can be inferred from this table. The generic model
also omits exceptional paths, recoding, normalization, inversion,
table access, and runtime overhead. `cpu_speedup_claim` is `null`.

The result retires the dense unit-digit path as a performance lead.
Further work should use this sparse control, charge a concrete
preparation chain, and compare native complete scalars with published
implementations in a host-isolated environment.

A later [prepared-orbit control](ORBIT_PREP_RESULT.md) implements the
paper's nine `ω`-image preparation multiplications and removes
on-demand digit rotations. Its evaluator count is the stronger
published-method stage reference; this table remains the frozen
first width-four comparison.
