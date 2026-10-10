# Grouped-unit gauge removes 78.6% of online cube-root products in U14

The opt-in secp256k1 U14 evaluator groups its fourteen selected affine
points by cube-root unit exponent and changes the four-limb Jacobian
accumulator's unit gauge between groups. It keeps the existing U14 table,
scalar representative, digit choices, and mixed-add count. The [proof](PROOF.md)
gives an at-most-two bound on nontrivial cube-root products per scalar;
the reference applies one to each selected point with exponent one or two.

## Exact-operation and correctness panel

| Frozen input set | Scalars | Reference beta products | Grouped-gauge beta products | Products saved |
| --- | ---: | ---: | ---: | ---: |
| Complete prior panels, boundaries, and new holdout | 33,292 | 310,754 | 66,351 | 244,403 (78.648%) |
| New post-protocol holdout only | 4,096 | 38,079 | 8,169 | 29,910 (78.547%) |

Every one of the 33,292 candidate evaluations used at most two gauge
products. The per-scalar reference and candidate counts are encoded in
[`gauge-panel.log`](gauge-panel.log); their decoded-byte SHA-256 is
`a9d60912eb172adf3b5418a3a7e615553d35c064a7d7e5f9c72f4dfdf4f804f4`.
The candidate matched the reference point, Eisenstein representative,
orbit/unit choices, mixed-add count, and table bytes on every input.
The first 128 new outputs matched an independent binary scalar multiplier.
The focused projective gauge test checked identity, equal and inverse
addends, plus 512 deterministic nontrivial sums with both cube-root powers.

The prospective [protocol](PROTOCOL.md) was committed as `ee53bf01a`
before generating the new seed-`20261010727` panel. Its scalar SHA-256 is
`f8721428414d861ec308267fb463c4636fddcc8aa6ee98f332298be202676c3c`;
the exact [input record](fresh-inputs.json) binds the prior panel hashes
and confirms disjoint reduced scalars. The full native release suite passed
**81/81** tests. Both CLI fixture modes independently verified all **129**
frozen expected points. The [verification receipt](verification.json),
SHA-256 `ce26749b195baa34ac1213da68f463cee0d61247ba8a659baec14478cb2ed4c5`,
binds 48 source/input/output files, test exits, the binary SHA-256
`db0d6527f2284e9eb0deac44f187a6c6d7d8a00b616689eae62f900d8c05d7e2`,
and the per-scalar count digest.

## Preparation and portability

| Same-binary resource case | Reference mode 126 | Grouped mode 127 |
| --- | ---: | ---: |
| Retained U14 table bytes | 70,430,960 | 70,430,960 |
| One-process peak RSS, macOS bytes | 278,085,632 | 278,167,552 |

Each RSS row comes from a fresh verified fixture-case process with
macOS `/usr/bin/time -l` outside the online timer. The first sandboxed
resource attempt failed because `kern.clockrate` was unavailable; its
stdout, stderr, and exit are retained separately. The two successful
processes had different allocator and host conditions, so the 81,920-byte
RSS difference is a diagnostic for these runs. Local CPU timer outputs
are retained as exploratory rows because this host has no isolation
receipt.

The x86-64 Linux target passed a release `cargo check` with Rustup stable
1.98 when both Cargo and rustc used that toolchain. The
[cross-check record](x86-cross-check.json) retains the successful log and
two prior toolchain-path failures. Physical x86 execution is queued for the
serial RunPod runner after the source snapshot is published.

The [paired manifest generator](make_isolated_manifest.py) produced nine
frozen fixture cases with five repetitions and structural SHA-256
`94d47d27ac82c2c0bba4c052dfc22ece4b5d78dde5c8843d90aecb7b104d2ef8`.
Its local CPU and NUMA identifiers are placeholders. A host-local
verification receipt and a passing strict isolated-benchmark preflight are
needed before interpreting a paired online wall-time ratio. The reachable
RunPod container fails that preflight, but can check physical x86
correctness under the serial experiment lock.

The construction uses the same unit symmetry underlying prior
endomorphism digit methods, including [Heuberger and Mazzoli's symmetric
digit sets](https://eprint.iacr.org/2013/705). Its class-reordered,
single-accumulator schedule avoids the extra projective bucket merges in
this repository's earlier tau-bucket formats. Literature priority for this
specific combination remains to be checked before an academic novelty
statement.
