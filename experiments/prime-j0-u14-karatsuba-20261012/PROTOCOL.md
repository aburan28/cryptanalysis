# Two-level Karatsuba Solinas scalar format

Format 170 keeps format 169's secp256k1 field, 14-window Eisenstein sector
digits, canonical affine table, XYZZ accumulator, and fixed scalar input law.
It replaces the generic 256-bit wide product inside direct Solinas field
multiplication with a two-level difference Karatsuba product. The first level
splits at 128 bits; each 128-bit product splits at 64 bits. The resulting
wide product uses nine variable 64-by-64 products instead of sixteen. The
Solinas fold and conditional subtraction are unchanged.

The wide-product assembly uses fixed carry chains and mask-selected signed
differences. It does not branch on field operands. The opt-in format retains
the same 1,004,908 affine entries and 64,314,208-byte table-plus-constants
accounting as format 169. Its extra temporary limbs are stack-local.

The frozen 4,096-scalar panel is
`../prime-j0-sector-digit-20261010/fresh-inputs.json`; the 129-case
independent CLI fixture is
`../prime-j0-secp256k1-native/tau6-comb13-bench-fixture.json`.

Correctness gates:

1. Compare the full 512-bit product against independent big-integer
   multiplication on boundary values and 10,000 deterministic random pairs;
   compare the reduced field product and square separately.
2. Compare all 4,096 scalar point and metadata records with format 169 and
   check the first 128 points through independent binary multiplication.
3. Rebuild the release CLI and check all 129 fixture rows, including scalar,
   base, expected point, mode, and verification marker.
4. Build the pinned Lean product identities and audit `#print axioms`.
5. Preserve source, binary, input, output, and proof hashes. Treat modeled
   limb counts as a source screen; require a paired full-operation run on a
   qualifying isolated host for a CPU wall-time claim.
