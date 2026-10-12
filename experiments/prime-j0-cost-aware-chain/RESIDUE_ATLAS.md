# Four-step τ residue atlas for one public scalar

## Frozen question and representation

The prepared width-4 τ evaluator currently obtains one τ digit per loop
iteration. This experiment replaces four consecutive digit iterations by a
compact, curve-independent residue atlas. It changes scalar recoding only:
the Eisenstein representative, nine seed points, point additions, τ schedule,
unit rotations, affine output, and correctness rules stay identical. The
target is lower complete prepared-scalar online time, including the atlas
lookup and point evaluation. This is an implementation hypothesis; it makes
no academic novelty or CPU speedup claim.

For `z = a + bτ`, use the exact identity `τ² = −3ω` with `ω³ = 1` and
`ω = 1 − τ`. Thus `τ⁴ = 9ω²`, and division by `τ⁴` after removing the
four-digit contribution `C = C_a + C_bτ` gives

`a' = ((a − C_a) + 3(b − C_b)) / 9`,
`b' = (−(a − C_a) − 2(b − C_b)) / 9`.

The width-4 digit choice at one position depends on the coefficient pair
modulo 9. Since `81` is associated to `τ⁸`, any two inputs with the same
coefficients modulo 81 have identical first four digits: after at most three
τ divisions their difference is still divisible by `τ⁵`, and therefore by
the digit-decision modulus `τ⁴`. Index the atlas by
`81 × (a mod 81) + (b mod 81)`. Generate all 6,561 indexes independently
with the existing exact digit rule; encode each as one of 217 patterns
(all-zero or one digit in one of four positions with one of 54 digit slots).
The lookup array takes 6,561 bytes and each pattern stores one byte each for
the digit slot, position, `C_a`, and `C_b`, for another 868 bytes. No table
construction belongs inside the timed scalar call. Generate the source table
deterministically and retain its generator, digest, and exhaustive controls.

For each scalar, choose the same minimum-L1 representative as the baseline,
then repeatedly apply one atlas lookup, append its four digit slots, and
advance by the quotient formula. Trim only trailing zero slots, cap at 256
digits, and preserve the baseline signed-wide fallback outside the safe
64-bit range. The source and generated table must be byte-for-byte stable
under regeneration. All 6,561 residues, signed translations by 81 in both
coordinates, random signed pairs, and boundary scalars must produce the
same digit stream and exact reconstructed scalar as the baseline.

## Prospective workload and decision

After this protocol is committed and its stacked PR is opened, generate four
new 4,096-scalar files on the two curves and public points in
[INTEGRATION.md](INTEGRATION.md). Use SplitMix64 state
`20261008 XOR (curve_index << 32) XOR point_index`; store reduced
little-endian `u64` values in original order. Freeze each input SHA-256 and
independent generic point-output digest before any isolated timing.

Compare the baseline prepared width-4 τ path with the atlas path on every
same point/scalar list. Both arms must replay every result against
`ca_group_mul` and have identical digit lengths, triples, additions, and
rotations. Preserve raw failures, input/source hashes, compiler, and output
digest. The online interval begins before lattice reduction and recoding,
ends after the last affine output is stored, and includes all four-step
lookups, point arithmetic, and conversion. Exclude process startup, input
loading, common seed preparation, and independent replay. This 4,096-scalar
panel measures prepared-scalar throughput; it does not replace a one-call
latency result.

Promote a speed claim only after at least five AB/BA pairs on a host passing
the repository's CPU/NUMA isolation and noise gates. Report all four cases
and uncertainty; a failed, noisy, or unverified pair remains a row and does
not become a win. Ordinary-host timings are exploratory. The algorithm is
variable-time and intended for public research scalars.

The τ-adic and fixed-base background is documented in
[ePrint 2012/519](https://eprint.iacr.org/2012/519.pdf); this protocol tests
a specific residue-table execution format against our current C path.
