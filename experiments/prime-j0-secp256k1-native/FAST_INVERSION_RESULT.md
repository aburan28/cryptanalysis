# Fixed-exponent inversion: correctness and isolated-run handoff

The field-chain and two native scalar modes were frozen in `11996e71`
before the release replay. The chain computes `x^(p-2)` with 257
field squarings and 14 multiplications; the old 256-round ladder
computes one multiplication and two squarings per round. The exponent
identity is proved in `FAST_INVERSION_PROTOCOL.md`. Since this native
field kernel currently implements squaring by calling the same
Montgomery multiply routine, the source-level inversion work drops
from **768 to 271 field-kernel calls**. This count does not predict a
CPU ratio: compiler output, memory effects, and the rest of scalar
multiplication must be measured together.

The checked Rust field test compared chain and ladder on curated
limb-boundary cases, zero, and 256 deterministic full-width residues.
For each nonzero input it also checked `x * inv_chain(x) = 1`.
The offline locked release build then replayed **all 320 frozen
secp256k1 scalar outputs**, comparing both inverse backends and the
independent fixture point. Four untimed one-case comparisons covered
every selector arm with identical echoed curve, base, scalar, source
cost, arm, and output point. `native-fastinv-checks.json` retains the
raw commands, exits, stdout/stderr, source and binary hashes, host,
and compiler. It reports `verified: true` with no failures; its SHA-256
is `70e257dfb086b70406b87207dde6cf7c50ce09d6ca45a33c02025aaec76b5cef`.
The replayed macOS ARM64 release binary SHA-256 is
`04515ce8f8f0ac5448dbc8c269f1d947ed8e401fc8723edbb489538de6eb9553`.

The paired manifest uses the same 256-case coset holdout for
`--benchmark-coset-case` and
`--benchmark-coset-fastinv-case`. Both complete scalar operations
include lattice reduction, four recoders, point setup and evaluation,
the selected inversion, affine conversion, and independent answer
comparison inside their timer. Only the inversion backend differs.
The structural manifest check is a handoff, not an isolation receipt.
Its synthetic-input manifest SHA-256 is
`770d7bf3353998ac631e0ca8c6fa4b987248400646ddc3a2a6740c6bc8816260`,
and `fastinv-manifest-schema.json` records the structural-only result.
No physical-host paired timing has run, so CPU speedup is **unknown**.
The addition-chain technique is established prior art; this is a
backend optimization and makes no scalar-scheme novelty claim.
