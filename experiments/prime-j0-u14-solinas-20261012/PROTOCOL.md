# Canonical Solinas XYZZ on the U14 sector schedule

Format 169 keeps format 168's 14-window Eisenstein sector digits, one XYZZ
accumulator, and grouped unit order. It stores the same 1,004,908 affine
table points as canonical residues modulo the secp256k1 prime
`p = 2^256 - 2^32 - 977`. All accumulator field multiplications and squares
use direct Solinas reduction: for a 512-bit product `L + 2^256 H`, fold
`L + (2^32 + 977) H` and its bounded carries modulo `p`. The 96-byte
cube-root constants remain canonical. The candidate retains 64,314,208 bytes
of table and Solinas constants under the established 64 MiB table cap; the
shared Montgomery cube-root cache is accounted separately in `RESULT.md`.

The source formula screen uses the frozen 4,096-scalar panel in
`../prime-j0-sector-digit-20261010/fresh-inputs.json`. Each ordinary mixed
XYZZ addition has eight general multiplies and two squares. The recorded
panel has 53,248 such additions and 8,167 unit rotations. The model charges
23 64-bit products to each direct Solinas field product, giving
`23 * (10 * 53,248 + 8,167) = 12,434,881` modeled products. Format 168's
corresponding Montgomery/Solinas model is 19,357,121. This model excludes
recoding, setup, final inversion/conversion, carry instructions, and cache
effects. Its purpose is to decide whether the implementation is worth a
controlled full-operation timing comparison.

Correctness gates:

1. Compare direct Solinas multiplication and squaring against independent
   big-integer arithmetic on boundary values and 10,000 deterministic pairs.
2. Replay all 4,096 frozen scalars against format 168, comparing the complete
   point and scalar metadata record. Check the first 128 points against
   independent binary multiplication.
3. Rebuild the release CLI and verify every scalar, base point, expected
   point, mode, and verification marker in the 129-case fixed fixture.
4. Build the pinned Lean theorem for canonical product reduction and output
   range; audit its declared axioms and preserve the written proof map.
5. Record the final source, binary, input, and output hashes. Keep CPU wall
   ratios exploratory until a paired, full-operation run has a passing
   host-isolation receipt under `../../docs/ISOLATED_BENCHMARKS.md`.

The unit-test process may hold both comparison tables. The standalone format
169 process prewarms only its own canonical table; retained candidate state
is measured for that process, separately from construction peak memory.
