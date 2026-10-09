# Deferred XYZZ mixed addition: bounded native implementation

The deferred XYZZ path carries raw Montgomery quotients through one generic
mixed addition, balancing only `H`, `R`, `X'`, `Y'`, `ZZ'`, and `ZZZ'`.
The current balanced XYZZ path invokes balancing 17 times in that addition;
the deferred path invokes it six times. Both perform the same ten field
products. The [frozen protocol](DEFERRED_PROTOCOL.md) proves a conservative
`760·2^128` upper bound on any raw output coefficient, within the checked
three-limb multiplication and four-corner balance limits.

The release binary passed the 645-scalar exact-output panel: 129 independently
supplied secp256k1 fixture points, `0`, `1`, `n`, `n+1`, and 512 frozen
SHA-256-derived scalars. For every scalar, Jacobian, balanced XYZZ, and
deferred XYZZ returned the same affine point, Eisenstein representative,
generic-addition count, and retained table bytes. The fixture contributed
1,677 generic additions. One single-case benchmark dispatch in each XYZZ
mode verified its expected point and timing-field schema. Those local timer
values are retained as raw output and excluded from the result comparison.

The machine-readable [receipt](xyzz-deferred-check.json) records the release
binary SHA-256 `d35afa20a336728c8986e0cc5e3b409c0e9a97cf30060497610de1caff4b5714`,
input SHA-256 `96e6cd9d2d6f02939b912fed2bc7c7f986b522ef28f6f5f67af447d6f872992c`,
all executed source hashes, the independent fixture hash, platform, and raw
output hashes. The emitted table payload was 78,470,208 bytes in all three
modes. `cargo build --offline --release` and the checker completed on ARM64
macOS. The release test for equal, inverse, and identity addends passed with
both affine and nonaffine accumulators. This is a correctness and
operation-schedule result; a paired
online wall-time result needs a strict isolated host receipt.
