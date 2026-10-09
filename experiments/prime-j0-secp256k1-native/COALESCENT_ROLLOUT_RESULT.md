# Exact coalescent comparison for redundant tau-four digits

The depth-two digit decision can be made by comparing nearby continuation
paths until they meet. This preserves the selected digits and point-formula
counts of the memoized suffix scorer while replacing its full suffix cost
maps with temporary paired paths. On the frozen 214-scalar panel, the native
coalescent mode agrees with the memoized mode on every representative,
`tau` step, addition, alternate-digit count, and independently verified
point. The coalescent mode records 145,533 deterministic first-digit
continuation transitions, 12,533 one-block expansions, and 7,369 zero
steps inside those expansions. These are integer recoding work counts;
the CPU effect needs a paired isolated-host measurement.

## Exact comparison rule

Let `B(z)` be the remaining point-formula proxy cost under the fixed first
digit of each nonzero residue class, with either table digit accepted as a
zero-cost terminal. Every transition decreases the Eisenstein norm, so
`B` terminates. If the paths from states `u` and `v` meet at `w` after
costs `c_u` and `c_v`, then

`B(u) - B(v) = (c_u + B(w)) - (c_v + B(w)) = c_u - c_v`.

The implementation advances the two paths alternately and checks each new
state against states already visited by the other path. If they reach
different terminal digits, both remaining costs are zero and the same
difference follows from their accumulated costs. Thus the comparator is
exact even when the paths do not meet early.

For each current digit choice, a depth-two decision first advances through
zero steps and one additional nonzero block. This leaves one terminal
outcome or two successor outcomes, each with a known prefix cost. The
comparator expresses every successor's `B` value relative to one common
reference successor, adds the prefix, and chooses the minimum. The shared
unknown `B(reference)` cancels, so this is exactly the memoized depth-two
choice, including the primary-digit tie rule.

## Frozen verification and use

The Rust unit test compares path differences against a full continuation on
2,401 pairs of small Eisenstein states and checks digit choices over the
`[-12,12]^2` state grid. All 37 release-mode Rust tests pass. The replay
checker verifies both native modes against the same 214-case JSON and
independent point multiplication:

```sh
cd experiments/prime-j0-secp256k1-native
cargo test --release --bin eisenstein_fixed
cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 check_redundant_tau4_native.py --mode redundant
PYTHONDONTWRITEBYTECODE=1 python3 check_redundant_tau4_native.py --mode coalescent
```

The memoized reference remains available as `--scalar-w4-redundant` and
`--benchmark-scalar-w4-redundant-case`. The new policy uses
`--scalar-w4-coalescent` and `--benchmark-scalar-w4-coalescent-case`.
Both benchmark case commands use the same fixed affine digit table and
target-dependent timer boundary described in
[`REDUNDANT_TAU4_NATIVE_RESULT.md`](REDUNDANT_TAU4_NATIVE_RESULT.md).
The replayed source SHA-256 is
`e0620110c63ec6c0e1b62cce2840fb5f2cbe004971d04700c530575231aa1233`;
the checker SHA-256 is
`a42f0d32dd4cf99a4b69cbc8c1ad30c92e4b8c12c68064b6a1224b44330fc54b`;
the release executable SHA-256 is
`aef1fa6e5cbd6ba0cc0f534a624844fcbc1c03e187516b3a08e1b413ccdf9445`.

The next experiment pairs complete scalar operations on a host passing
the strict isolation preflight, with each scalar and process envelope
frozen. The current RunPod pod's failed preflight leaves that CPU comparison
open. The coalescent mode is optional until such a comparison is recorded.
