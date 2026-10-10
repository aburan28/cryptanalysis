# Exact reciprocal selection of Eisenstein lattice corners

The existing fixed-generator U14 scalar path reduces a scalar to the four
hexagonal lattice corners and chooses the smallest Eisenstein norm. Two
online quotients, `floor(k*v1/n)` and `floor(k*(-w1)/n)`, locate that cell.
This experiment replaces those divisions with products by precomputed
integer reciprocals. The four corners, their ordering, the digit stream,
and the point table remain the comparison invariant.

## Exact quotient identity

The subgroup order `n` is prime and `0 < c < n`, where `c` is either
`v1` or `-w1` from the committed `SCALAR_LATTICE`. Define

`R_c = floor(2^512*c/n)`.

For every reduced `0 <= k < n`, the candidate cell coordinate is

`q_c(k) = floor(k*R_c/2^512) = floor(k*c/n)`.

For `k=0`, both sides vanish. For `0<k<n`, primality and `0<c<n` imply
`k*c mod n >= 1`. The reciprocal truncation error after multiplying by
`k` is less than `k/2^512 < n/2^512 < 1/n`, because `n<2^256`.
The exact rational quotient has a fractional part of at least `1/n`,
so the truncation cannot cross the preceding integer. The candidate
therefore obtains the *identical* four corners without a correction
branch or integer division. The 512-bit shift is a proof parameter,
not a measured optimum.

This is a fixed-base public-scalar experiment. Reduction of arbitrary
input to `[0,n)` and conversion to the output type are charged in a
complete online timer. A future fixed-limb implementation must verify
the constants and full product width at startup or compile time.

## Frozen comparison

1. The reference is `hexagonal_four_corner_choices` on the parent
   `codex/prime-j0-staged-prefetch-20261010` snapshot. The candidate
   computes each floor using `R_c`, constructs the same four corner
   coordinates, sorts by `(Eisenstein norm, maximum absolute coordinate,
   a, b)`, then uses the existing signed-word U14 table evaluator.
2. Check every exact quotient, all four ordered corners, the selected
   representative, the fourteen orbit/unit choices, nonidentity-add
   count, retained table bytes, and final point. Use the 519 frozen
   scalar inputs and a disjoint fresh panel of 4,096 scalars generated
   by `random.Random(20261010163)`, with zero and `n-1` boundary cases.
   Verify at least 128 fresh points by an independent binary group law.
3. Retain the protocol, constants, input, source, binary, raw outputs,
   command exits, and architecture/compiler hashes. A Python theorem
   audit precedes native integration and must include exhaustive small
   prime controls where the theorem's assumptions hold.
4. For any online CPU comparison, pair the candidate with the same
   signed-word U14 point on a physical host passing
   `docs/ISOLATED_BENCHMARKS.md`. Charge scalar reduction, both products,
   all corner scoring, signed-word recoding, table lookup, point work,
   conversion, and verification. Preserve failed and noisy rows.

The fixed-point quotient technique has prior use in GLV scalar splitting,
including Bitcoin Core's `scalar_mul_shift_var`. This experiment tests
exact floor equivalence for the specific hexagonal four-corner selector
and its complete U14 execution path; a literature review is required
before attributing academic priority to that combination.
