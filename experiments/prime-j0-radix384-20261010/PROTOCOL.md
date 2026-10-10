# Fifteen-window radix-384 Eisenstein scalar format

Mode 133 expands the certified secp256k1 Eisenstein representative in
fifteen uniform radix-384 digits. Its point table stores one affine point
per orbit under the six Eisenstein units in each window. The primary
comparison is mode 131, which also uses fifteen windows and at most
fourteen mixed additions. Radix 384 trades a smaller point table against
nonbinary quotient and residue work.

Freeze this protocol, proof, generator, and implementation in a commit
before generating the 4,096-scalar panel with seed `20261010134`.
Reduced scalars must be unique and disjoint from the preceding thirteen
panels. Enumerate all 147,456 residues to check the signed digit, orbit
rank and unit code. Check every one of the 368,670 precomputed point
slots by independent group multiplication. For every new scalar, compare
mode 133 with modes 130 and 131, its representative, digit choices,
operation counts, and scalar reconstruction; check the first 128 points
with independent binary multiplication. Check all 129 fixture points and
the full release suite. Preserve source, input and binary hashes, raw
outputs, failures, and peak RSS.

For a later controlled timing panel, pair modes 131 and 133 on the same
public scalar, same binary, and same host resource envelope. The online
interval begins with scalar reduction and ends after point verification;
it includes representative selection, all quotient and residue work,
table lookup, unit grouping, additions, inversion and formatting. Table
construction is reusable setup and recorded separately. A CPU speedup
requires a passing host-level receipt under `docs/ISOLATED_BENCHMARKS.md`.
The existing RunPod container can run correctness replay through its
serial lock but fails that isolation gate.
