# Prepared field arithmetic for independent curve checking

This experiment changes Python field arithmetic in the independent public-point
curve checker. The F4 producer, algebraic checker, native curve-witness producer,
curve identities, original equations and full public-target checks are unchanged.
Every query still has fresh descent, solving, proof and curve witness production.

Three predeclared arms separate the effects:

| Arm | Multiplication | Squaring |
| --- | --- | --- |
| baseline | Original Python polynomial shift/XOR | Original multiplication |
| squares | Original multiplication | Prepared binary linear map |
| packed | Exact integer packing, with a small-operand path | Prepared linear map |

Only field-dependent immutable tables and masks persist. At degree 31 the
squares arm has 1,024 table entries. Packed adds 1,024 reduction entries and
bit-permutation masks. These are ring preparation, outside all online query
intervals; input conversion, multiplication, coefficient extraction, reduction
and every independent check remain inside each query interval. No field
products or target answers are cached. Existing solver dispatch is unchanged.

## Exact arithmetic argument

For a binary polynomial `a(X)`, squaring is linear: the coefficient of `X^(2i)`
is its input bit `a_i` and odd coefficients vanish. Each table maps an input
byte at a fixed offset to its squared polynomial reduced modulo the field
polynomial. XORing these byte images gives the exact field square.

For multiplication, map `a(X)` to the ordinary integer `a(256)`. Every integer
convolution coefficient of two degree-`<n` binary polynomials is at most `n`.
For `n <= 255`, it fits in one base-256 digit, so no inter-digit carry occurs.
The low bit of every digit in `a(256)*b(256)` is exactly the corresponding
coefficient of the product over GF(2). Shift/mask permutations pack and gather
the bits; prepared linear byte tables reduce the upper polynomial coefficients.
The test suite demonstrates a wrong parity at `n=256` and rejects that shape.

Commutativity selects the smaller multiplier. Zero and one have direct paths;
a multiplier below 16 uses at most four iterations of the reference operation.
Larger products use the packed path. Canonical input ranges are checked. The
field kernel supports degrees 1..255; the surrounding round63 native witness
producer still supports odd degrees 3..63, and the query checker requires an
odd degree. The complete-query panel uses the original degree-31 fixtures.

This is an application of established Kronecker substitution, also documented
in [FLINT's polynomial algorithms](https://flintlib.org/doc/mpn_mod.html#polynomial-algorithms)
and [Sutherland's lecture notes, section 3.6](https://math.mit.edu/classes/18.783/2019/LectureNotes3.pdf).
No FLINT implementation is imported. The finite-degree packing bound and the
reduction-table storage limit the scope; this experiment establishes no new
asymptotic Gröbner algorithm or F6 novelty.

## Evidence and reproduction

The retained profile of 100 reference witness checks counts 3,400 field-product
calls: 1,800 multiplications and 1,600 squarings. A separate five-check operand
profile finds 45 of 90 nonsquaring products have a <=2-bit smaller operand.
These are instrumented diagnostics, not measured speed ratios.

From the repository root:

```sh
python3 -u experiments/groebner-perf-20260924/round64/run_validation.py --output /tmp/packed-field-evidence
```

Use a new output directory. The workflow rebuilds native dependencies, runs
16 unit groups, validates 138 complete/algebraic query records, attempts the
frozen three-arm timing panel, and independently audits sources, binaries,
proofs, witnesses and phase accounting. CI rebuilds on Linux x86-64 and hosted
macOS ARM64. Offline artifact audit does not load foreign native binaries.

The full paired query comparison, not this operand profile, determines whether
packing beats its overhead. All three trials of seven measured pairs on every
primary case must qualify and have a lower bootstrap ratio bound above one
for baseline/packed. Squares-only remains a separately reported ablation.
A further 2x gain is a target. Planted controls are not natural relation yield
or complete one-target IC recovery; those identifiers and speedups remain null.
