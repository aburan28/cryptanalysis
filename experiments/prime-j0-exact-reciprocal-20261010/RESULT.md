# Exact reciprocal hexagonal selector for fixed-base multiplication

The opt-in secp256k1 U14 evaluator computes its two hexagonal lattice-cell
coordinates with fixed-limb products and a 512-bit shift. It selects the
same four corners and the same minimum-norm representative as the divided
U14 selector. Each coordinate uses a 256-bit scalar times a precomputed
385-bit-or-smaller reciprocal; the native hot path performs no wide integer
division for these two coordinates. The signed-word recoder, fourteen
table entries, unit actions, mixed additions, and 78,470,208-byte point
table are shared with the reference.

The [protocol](PROTOCOL.md) gives the exact quotient proof. Since the
secp256k1 subgroup order is less than `2^256`, reciprocal truncation at
`2^512` perturbs `k*c/n` by less than `1/n`. For nonzero reduced `k`, its
fractional part is at least `1/n`, so the floor is unchanged. The native
implementation verifies both reciprocal constants against the lattice
definition before benchmark timing begins.

The [theorem screen](screen-result.json) passed **989,694** exhaustive
small-prime quotient checks and matched both quotients and all four
ordered corners on **4,617** secp256k1 inputs: two explicit boundaries,
the 519 frozen inputs, and 4,096 disjoint fresh scalars. All selected
representatives preserved the scalar modulo the subgroup order. An
independent Python group law replay matched **128** fresh points. The
largest selected coordinate occupied **129 bits**. The fresh input digest
is `6617a018073c382e60c9338c566dbf7677db5f5d604f8f2d886463a127a70269`.

The [native receipt](verification.json) records a release executable SHA-256
of `d0d9c98d34c53f87df1cda8772235d5bca4bf311678aa69eaa05f8aa9e151aef`.
The complete release suite passed **68 tests**. Its new test compared
the exact quotients, ordered corners, representative, addition count,
retained table bytes, and final point with signed-word U14 on all
**4,615** frozen and fresh scalar inputs; the first 128 fresh outputs
also matched independent binary double-and-add. Both fixture modes
verified all **129** expected points, and both benchmark-case entrypoints
verified the same point. The receipt retains source, input, binary, raw
output, command, and exit hashes. A release-mode cross-compile check for
`x86_64-unknown-linux-gnu` passed with Rust 1.98; the
[build receipt](build-receipt.json) retains both commands, raw logs, exit
codes, and binary hash. Physical x86 execution is the next backend
correctness check.

The [isolated panel](ISOLATED_PANEL.md) pairs the two modes on nine frozen
fixture scalars with five repetitions. Its manifest passed local structural
validation with SHA-256
`13765ed226c933a0c395d911b553d659c631a4521b769b303f3155c853ca1149`;
the CPU and cgroup values used for that check were placeholders. Its timer charges complete online
selection and point evaluation, including scalar reduction and expected
point verification. The reachable RunPod CPU Pod fails the host-level
isolation preflight, so the source-level removal of two divisions is an
implementation result; the complete CPU wall-time effect awaits a
qualifying host. [Bitcoin Core's GLV splitter](https://github.com/bitcoin-core/secp256k1/blob/master/src/scalar_impl.h)
uses fixed-point products for a related scalar decomposition. The contribution tested here
is the exact-floor, correction-free construction of the four ordered
hexagonal candidates inside this U14 path; an independent priority review
is needed for an academic novelty claim.
