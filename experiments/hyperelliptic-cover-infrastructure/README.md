# Hyperelliptic cover infrastructure

This directory records the bounded library mirror from
[`aburan28/crypto`](https://github.com/aburan28/crypto/tree/3b8664a466efd56121509cd77866a07e3cb55741),
pinned to implementation commit `3b8664a466efd56121509cd77866a07e3cb55741`.
The upstream
[audit and evidence](https://github.com/aburan28/crypto/tree/d167ce0af49c22947b6d40f373b35df75e13e82e/research/hyperelliptic_cover_infrastructure_20261006)
separate curve construction, Jacobian arithmetic, transfer, subgroup
preservation, and measured advantage. The upstream standalone
[`hyperelliptic-cover`](https://github.com/aburan28/crypto/blob/3b8664a466efd56121509cd77866a07e3cb55741/src/bin/hyperelliptic_cover.rs)
command exposes the certificate replay and structured arithmetic interface.
This mirror intentionally adds no solver, CLI, or generated catalog.

## Supported boundary

- `binary_cubic_pullback_v1` constructs and checks the same-field separable
  degree-three map from its genus-three, one-infinity binary source to an
  ordinary binary elliptic curve. The library supports checked Mumford
  arithmetic, rational source-point pushforward, pullback of rational
  elliptic point classes, typed witnesses for
  `phi_* phi^*([P]-[O]) = [3]([P]-[O])`. Pullback is injective only if the
  supplied integer is independently established as the exact subgroup order
  and is coprime to three; the API does not prove that caller precondition.
  When three divides the order, the kernel intersection remains unresolved.
- Odd-characteristic arithmetic accepts only deterministically validated odd
  prime moduli of at most 64 bits and smooth monic squarefree models of exact
  degree `2g+1`, with one rational point at infinity. Its exhaustive
  `F_{p²}` counter uses an immutable, checked nonresidue context and the
  explicit `p ≤ 4096` enumeration bound. It explicitly rejects the upstream
  `prime_quadratic_pullback_v1` genus-two sextic: that source has two rational
  points at infinity and needs a different Jacobian representation.

Arbitrary-Jacobian pushforward, generic pullback/pushforward across cover
families, prime even-degree/two-infinity Jacobian arithmetic, full-Jacobian
relation collection or target decomposition, production key recovery,
calibrated costs, matched rho, and any end-to-end speedup are unsupported or
not established. A bounded unsupported result is not a nonexistence result.

## Quartic PR #290 is a separate norm projection

Cryptanalysis [PR #290](https://github.com/aburan28/cryptanalysis/pull/290),
paired with crypto [PR #1389](https://github.com/aburan28/crypto/pull/1389),
studies the genus-three **nonhyperelliptic plane quartic**
`C: v^4 = x^3 + ax + b` and `pi(x,v) = (x,v^2)` over tiny prime fields.
It certifies complete line sections, but forms its linear system only after
elliptic norm projection. Its columns identify projected elliptic images,
not divisor classes in the full `Jac(C)`; deck-conjugate divisors can differ
in the Prym component. The retained fixture and controls therefore establish
bounded norm-projection correctness, not a hyperelliptic construction,
full-Jacobian index calculus, scaling, or a speed result. See the mirrored
[`quartic kernel`](../../suite/src/cryptanalysis/bielliptic_quartic.rs),
[`quartic-ic` command](../../suite/src/bin/quartic_ic.rs), and
[`replay check`](../../tools/check_bielliptic_quartic.mjs).

## Source parity

The implementation source is crypto commit
`3b8664a466efd56121509cd77866a07e3cb55741`; the original audit baseline is
`5874ce8b393dccc4c735cc7ca5a47de7fe196c59`. The SHA-256 values below record
the mirrored file identities. From the repository root, run
`cargo run --locked --manifest-path suite/Cargo.toml --bin hyperelliptic-source-parity --`
to verify the local mirror. Append `--crypto-root PATH` after `--` to also
verify a crypto checkout.

| Crypto source | Cryptanalysis mirror | SHA-256 status |
| --- | --- | --- |
| `src/binary_ecc/hyperelliptic.rs` | `suite/src/binary_ecc/hyperelliptic.rs` | exact: `09ce8a689aa8e190f51c871f9e94467271ea731b9629f69d322ae716de507c5c` |
| `src/binary_ecc/cover_transfer.rs` | `suite/src/binary_ecc/cover_transfer.rs` | exact: `67b94112f70becf100ccc2cc7e0b3bc057e5663a4019b63fe966de9e62fd5069` |
| `src/binary_ecc/mod.rs` | `suite/src/binary_ecc/mod.rs` | adapter: source `84ece02cbf6f897317b236239c47efb0738d0e8e9f3d8530d2d4793609426099`, mirror `2ee3eddf1f1ce3985a850b338861ca57c66c6674716384b31cdac92d7d7e5a29` |
| `src/prime_hyperelliptic/curve.rs` | `suite/src/prime_hyperelliptic/curve.rs` | exact: `7a769bfb7abfe92ce06da7c02340f2a2426827d8066ebef510375149b8c3d5ad` |
| `src/prime_hyperelliptic/fp2.rs` | `suite/src/prime_hyperelliptic/fp2.rs` | exact: `b833bdff5247f2eea0cde7feb89d0378cfe8305671f9065d2dae7ab538c03e55` |
| `src/prime_hyperelliptic/mod.rs` | `suite/src/prime_hyperelliptic/mod.rs` | exact: `b6906f75b4d0eb6b7ac406a0fca1b2cef1786a528d4aedbab414e9fa1e7f7662` |
| `src/prime_hyperelliptic/fp_poly.rs` | `suite/src/prime_hyperelliptic/fp_poly.rs` | selected domain-binding adapter: source `b5d1a1ba5e95d8d0dd06b71757567fb559adbdd09b1ab623ae76e0049ee593c2`, mirror `44f7af14d22bed78d85c4bd009ccce7197fa9257e7ff56164c8d891303e49590` |

The binary module adapter preserves two existing unlinked rustdoc references
for private field helpers; its executable declarations and exports are
otherwise byte-equivalent after that normalization. The polynomial adapter
ports the required coefficient-field equality guard and regression test,
while preserving cryptanalysis's pre-existing lack of crypto's unrelated
`pow_mod` helper. Exact machine-readable identities and adapter rules live in
[`source-parity.json`](source-parity.json).
