# Fixed-exponent inversion backend for full scalar output

This backend replaces only the final projective-to-affine field
inversion in the `coset_fastinv` mode. Both paired modes use the same
scalar reduction, three-representative selector, four recoders, seed
preparation, point evaluation, and expected-point comparison. Keep the
existing `coset` mode as the reference in the same native binary.

For secp256k1's field prime `p = 2^256 - 2^32 - 977`, inversion of a
nonzero field element is exponentiation by
`p-2 = 2^256 - 2^32 - 979`. Let `t_k = x^(2^k-1)`. The fixed chain
constructs `t2,t3,t4,t8,t11,t22,t44,t88,t176,t220,t223` and `x^45`,
then returns

`(t223^(2^23) * t22)^(2^10) * x^45`.

The exponent is
`(2^223-1)*2^33 + (2^22-1)*2^10 + 45 = p-2`.
Count every `sqr()` and `mul()` in the implementation: **257 squarings
and 14 multiplications**. The existing 256-round ladder evaluates one
product and both candidate squares each round: **512 squarings and 256
multiplications**. The current Montgomery squaring dispatches to the
same underlying multiply kernel, so this is a reduction from 768 to
271 field-kernel calls for inversion. Actual wall-time improvement
remains unknown until isolated paired timing.

Both exponent schedules are fixed independently of the field element.
The chain returns zero for zero, matching the old routine. This does
not certify a constant-time implementation at the hardware level or
authorize secret-scalar use of the variable-time scalar selector.

Before any CPU claim, require the chain/ladder test on curated and
deterministic full-width field elements, native replay of all frozen
scalar outputs with both inverse backends, and a physical-host
isolation receipt comparing the complete `--benchmark-coset-case` and
`--benchmark-coset-fastinv-case` operations on identical inputs. The
timed interval must include affine inversion and expected-point
verification. A structural manifest check alone is insufficient.

Fixed field-inversion addition chains have extensive prior art,
including the [addchain project](https://github.com/mmcloughlin/addchain).
This backend is an implementation optimization, not an academic
novelty claim for scalar multiplication.
