# Native mixed-radix replay gate

Freeze `src/mixed_radix.rs`, its dispatch in `src/main.rs`, this
protocol, and `make_mixed_radix_seed_fixture.py` before native release
replay of the saved 64-case design and 256-case fresh panels. The
candidate recoder and fresh scalar fixture were frozen separately,
before the fixture existed.

Use the checked Sage launcher to generate the independent twelve-orbit
point coordinates for the eight fresh bases. Build the Rust crate with
`cargo build --offline --locked --release`. For every case, recompute
the short scalar representative and both candidate paths natively.
Compare per-case greedy, selective, and chosen source costs and arm
choice to `mixed-radix-scalar-result.json`. Use the same compact FNV-1a
byte encoding in Python and Rust to check the complete greedy action
sequence for every case. The fingerprint is a cross-language
regression control, not a cryptographic commitment; the frozen scalar
fixture and point output checks remain authoritative.

For a chosen radix-two path, verify all nine prepared original seeds
against the fixture, execute the exact interleaved double/τ/Jacobian
path, and recount every τ step, fused pair, double, mixed/general add,
and cache entry from executed operations. For a chosen selective path,
verify each built seed against independent Sage coordinates and use
the existing native selective evaluator. Require every final affine
point to match the scalar fixture; retain exceptional cached-add
counts and raw process failures. The release binary and all source,
fixture, runtime, and receipt hashes belong in the replay record.

This is a correctness/source-accounting gate only. The selected path
computes two recoders and must be timed in full on a physical host
that passes the repository isolation preflight before any CPU
performance claim. It remains variable-time research code.
