# Direct fixed-limb reconstruction for certified U14 multiplication

The new opt-in secp256k1 U14 mode constructs the certified nearest
Eisenstein representative directly from reciprocal quotient limbs. It
converts the reduced scalar to four limbs once, performs two fixed 4-by-7
reciprocal products, certifies the corner from their high fractional limbs,
and forms the signed coordinates with four fixed 3-by-3 limb products.
The U14 table, signed-word recoder, point operations, and correctness
check remain shared with the parent certified mode.

The [protocol](PROTOCOL.md) proves the six-limb intermediate and
three-limb output bounds. Ambiguous corner intervals still use the exact
parent selector. The native test compared selected corners, signed
coordinates, addition counts, table bytes, and complete points for
**12,811** boundary and frozen scalar inputs: four boundaries, 519 original
inputs, two prior 4,096-scalar panels, and a [new disjoint 4,096-scalar
holdout](fresh-inputs.json). The first 128 new holdout points also matched
independent binary double-and-add. The holdout scalar digest is
`6b0b278990ff158693b3b03e52ae511e2acd17d93a0ad73c8658407b15049a3e`.
All examined inputs received a unique interval certificate.

The [verification receipt](verification.json) binds the final source,
input law, executable, release test log, and raw fixture outputs. All
**70 native release tests passed**. Both modes verified all **129** fixture
points and emitted equal per-case fields apart from their mode labels.
The release binary SHA-256 is
`55b13293731aa79634ef3ed4c398cf3f40353d29fd2ccc210428bc3ef1599d33`.
The [x86 cross-check](x86-cross-check.log) compiled the release code for
`x86_64-unknown-linux-gnu` with Rust 1.98; physical x86 execution is
still a separate check.

For a certified scalar, reciprocal multiplication performs 56 fixed
64-by-64 partial products and coordinate reconstruction performs 36.
The candidate replaces the parent's four BigInt coordinate products with
the 36 fixed partial products and small limb additions/subtractions.
Scalar reduction and diagnostic conversion to BigInt remain in the
complete online path. A wall-time result needs the paired
[isolated panel](ISOLATED_PANEL.md) on a qualifying host. The existing
RunPod CPU container fails that host gate.
