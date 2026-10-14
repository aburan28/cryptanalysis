# Binary genus-two cover and Jacobian transfer

Construct a cover of `E_a: y²+xy=x³+a*x²+1` over the **same binary field**:

```
C_a: v²+u²*v = u⁵+a*u⁴+u³+u
pi(u,v) = (u³/(u+1)², (u*(u+1)*v+u²+u+1)/(u+1)³).
```

The smooth projective source has genus two. Its infinity and points above
u=1 map to E's origin; (0,0) maps to (0,1). The curve is one-dimensional;
its Jacobian is an abelian surface, where the group law lives.

The library `GenusTwoCover` checks the model with the repository's existing
`HyperellipticCurve` and `MumfordDivisor` implementation, supplies the point
map, pulls elliptic point classes into the Jacobian, and inverts that image.
The library accepts validated polynomial-basis fields supported by the
backend and any coefficient a of that field; b is fixed to one. The CLI
only accepts the existing pinned GF(2^83) a=0/a=1 fixtures.

From the repository root:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml -- \
  --a both --output /tmp/genus2-n83.json
```

Default Q is the public fixture 37P. To transfer a supplied public point on
the **exact same model, basis and subgroup**, choose one a:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml -- \
  --a 0 --q-point 0x590a9c0709b34b0bcd3d4,0x6aa49dc52796827db931a \
  --output /tmp/genus2-supplied-q.json
```

Omitting `--scalar` in supplied-Q mode leaves both scalar fields null. Add a
known witness only to check it. Invalid input or a failed check exits 2.
The basis is `z^83+z^45+z²+z+1`. Exact subgroup orders are decimal strings;
field elements and ascending Mumford coefficients are hexadecimal strings.
For a=0 the command reuses the cited historical Sage prime receipt. For a=1
it performs a fresh deterministic u64 seven-base Miller–Rabin check.

For nonzero x, the reduced pullback is

```
U(u) = u²+(1/x)*u+x
V(u) = (x+(y+1)/x²)*u+x+y+1.
```

O maps to `(1,0)` and (0,1) to `(u,0)`. The checked inverse on this image
recovers x=U(0), y=V(0)+x+1, then reconstructs and compares the full pair.
A valid Jacobian divisor outside the image is rejected. Arbitrary-divisor
norms are not implemented. By Picard pullback this is a homomorphism; the
explicit inverse and uniqueness of reduced pairs establish injectivity.
Independently, `pi_* pi^*=[3]` proves injectivity on order-r subgroups with
gcd(3,r)=1, including both pinned fixtures.

Run `tools/binary-genus2-cover/check.sh` for formatting, native tests,
Clippy, CLI checks, and integer-lift identity replay. The exact identity
certificate has its own executable:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml \
  --bin genus2_identity -- /tmp/fresh-genus2-identities
```

The output directory must not already exist. See the
[protocol](../../research/binary_genus2_cover_20261014/PROTOCOL.md) and
[report](../../research/binary_genus2_cover_20261014/REPORT.md) for the
geometric proof, recorded checks, Lean proof scope, and PDF.

No field descent, independent-host verification, unknown-log recovery,
generic cover search, or faster ECDLP solver is established. Arithmetic is
variable-time research code.
