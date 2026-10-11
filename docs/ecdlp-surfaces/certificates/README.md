# Native identity-certificate replay

This small Rust package records the two algebraic identities used by the
surface tools and the exact EC1 metadata of the public arithmetic fixture.
It is separate from the three dependency-free command-line tools.

From this directory:

```sh
cargo test --locked
cargo run --release --locked -- ../evidence
```

An exact integer-coefficient expansion checks each identity before issuance.
The `identity.certificate/v1` checker then replays 32 statement-derived points
over the schema's field `2^61-1`, plus 32 further points from a separate seed.
The negative tests reject a false identity and a corrupt value digest. These
checks run on one host; they are not a second-host replay or a formal proof.

The shared checker is a source snapshot of
[`src/cryptanalysis/identity_certificate.rs`](https://github.com/aburan28/crypto/blob/de6ff17ad4608d94f6eb9e934b2483f6f291ed69/src/cryptanalysis/identity_certificate.rs),
retaining its implementation through `check_with_extra` and omitting the
unrelated worked example and tests. Its source file SHA-256 is
`d81ee915ad769a87d7aac5d9664631239607f4a0deb27850cdb52cea84e34270`.
The portable SHA-256 code is the prefix through `sha256` of
[`src/hash/sha256.rs`](https://github.com/aburan28/crypto/blob/de6ff17ad4608d94f6eb9e934b2483f6f291ed69/src/hash/sha256.rs),
whose complete source file SHA-256 is
`2bafe271f1b2f6e6eb1a100f672f81e2b16bbe30b6db29ac579c0740dfe9eddf`.
These snapshots make the same replay available in both repositories without
building their larger libraries. EC1 bytes follow `docs/curve-identities.md`.

The curve record identifies a public known-answer fixture, not an IC candidate,
factor base, new isogeny route, or measured solver result. No catalog or
performance-state promotion is made by this package.
