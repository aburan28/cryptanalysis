# Direct-limb scalar intake for Eisenstein U14 multiplication

The opt-in mode accepts a four-limb unsigned 256-bit scalar and keeps its
reduction and certified Voronoi representative in fixed limbs through the U14
point evaluator. Because the secp256k1 subgroup order exceeds `2^255`, one
comparison and at most one subtraction reduce every such input modulo the
order. The point evaluator is shared with mode 124, and both modes use the
same binary-GCD affine finalizer. The new path avoids arbitrary-precision
scalar reduction and the parent path's post-computation conversion of the
representative back to `BigInt`. Signed or wider inputs retain the mode-124
arbitrary-precision path.

## Correctness record

The native release suite passed **76/76** tests. The limb reduction and
selector test compared four order/range boundaries and 512 deterministic
256-bit inputs with the arbitrary-precision residue, representative,
corner certificate, fallback status, addition count, and table payload. The
complete point comparison matched mode 124 on **25,100** boundary, prior-panel,
and disjoint new inputs; 128 new points also passed independent binary scalar
replay. Both modes verified all **129** frozen secp256k1 fixture points. The
[verification receipt](verification.json) binds the source, input, release
binary, native test log, fixture outputs, and exits. Its release binary
SHA-256 is
`8d6231bfed3152b974459948fb63e4199f70bb62f8278fc8a978cac6f2508507`.

The 4,096-input holdout was generated after protocol commit `36981e1a1`
with seed `20261010625`. The scalar digest is
`287f19a7474da3ec320d852128e82b18ddf5ac78dc63ae256235db24702ecf74`.
The x86-64 Linux release cross-compilation check passed with Rustup's
installed target. Physical x86 execution remains the queued replay's gate.

## Paired measurement

The [isolated manifest generator](make_isolated_manifest.py) pairs modes 124
and 125 on nine frozen fixture indices for five repetitions. The online
interval starts after fixture loading and scalar decoding, includes the
target-dependent reduction, point work, affine conversion, and expected-point
verification, and stops after that verification. The input representation
conversion is recorded in preparation; the primary online comparison starts
from each mode's ready scalar representation. An encoded-input comparison
must charge this preparation to both arms separately.
The local manifest structure check emitted nine cases and five repetitions
with SHA-256
`2b5436253d165f3b430165b23fc8b90bacfe4d4ceae1ea8a1d98108b5700c362`;
its CPU and NUMA identifiers were placeholders.

The existing RunPod serial queue is suitable for x86 correctness replay.
Its Docker/cgroup-v1 host has no auditable isolated CPU partition, so a
controlled wall-time ratio awaits a host passing the repository's strict
isolation and noise gates. The local suite and fixture checks establish
correctness under the stated inputs and do not supply that timing result.
