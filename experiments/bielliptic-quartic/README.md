# Native bielliptic quartic diagnostic

The `quartic-ic` command implements the exact line-relation mechanism for
`C: v^4=x^3+a*x+b -> E: y^2=x^3+a*x+b`. It collects complete rational
line sections, verifies their multiplicities and elliptic norm sums, and
uses their projected relations to recover a supplied small-field target.
The reusable API is `cryptanalysis::bielliptic_quartic` in both Rust crates.

Run from the crate root (the repository root in crypto; `suite/` in
cryptanalysis):

```sh
cargo run --release --bin quartic-ic -- demo
cargo run --release --bin quartic-ic -- collect --p 53 --a 2 --b 1
cargo run --release --bin quartic-ic -- solve \
  --p 53 --a 2 --b 1 --generator 0,1 --target 29,42
```

For a dependency-free replay, from either repository root:

```sh
bash tools/check_bielliptic_quartic.sh
```

The command emits deterministic JSON with exact field/curve/subgroup/
generator records, shared EC1/curve UIDs, source hashes, complete line
certificates and their content hash, factor-base points and their hash,
preparation counts, failures, target-fiber witnesses and scalar replay.
The fixed `demo` constructs a known-answer fixture before preparation;
`solve` takes the target point only. Neither preparation nor recovery
accepts the fixture's scalar. `collect` also works when the elliptic
group order is composite; `solve` rejects that unsupported case.

## Mathematical scope

For this plane quartic, the infinity line cuts out `4*R_infinity`.
A finite line therefore gives `sum_i [R_i-R_infinity]=0` in `J(C)`.
Two known intersections leave a polynomial of degree at most two.
The verifier independently reconstructs the entire section polynomial,
including repeated roots and infinity, then replays its norm sum on E.
A zero elliptic sum alone is not an accepted quartic certificate.

The matrix is over the prime elliptic group order, AFTER the norm
projection. Its columns fold elliptic negation and repeated norm images.
These columns are not a factor-base representation of the full Jacobian;
deck-conjugate divisors can differ in the Prym component. Preparation
anchors one known generator multiple, solves the projected relation
matrix and replays every recovered factor-base log. The target stage
finds a signed rational fiber of a shifted target, retaining both points
in its degree-two pullback divisor and checking the recovered scalar.

The API enforces prime moduli between 5 and 257, canonical coordinates,
nonsingularity and independent pair/target budgets. Unsupported
characteristic two, extension fields, larger fields and nonprime group
orders never silently enter a different solver. Exhausted budgets and
insufficient rank remain failed cells, with no rho or log-search fallback.

## Verification, not a speed claim

The fixed replay has 45 rational quartic points, 79 certified sections,
22 distinct nonidentity norm images, 11 folded matrix columns and rank
11 (one anchor plus ten independent line rows). All eleven factor-base
logs replay, and the supplied target returns the verified scalar 17.
The native tests cover every scalar in the order-59 correctness fixture,
all 990 secant pairs, certificate tampering, repeated intersections,
infinity, unsupported input and failure budgets. These are known-answer
controls, not a natural-yield or performance benchmark.

The [correctness record](evidence/correctness-control.json),
[failed controls](evidence/failure-controls.json) and
[local verification receipt](evidence/receipt.json) retain exact outputs
and source hashes. Repository CI validates the delivered snapshot separately.

Timing, calibrated total operations, rho comparison, candidate ID and
speedup remain null. The published O-tilde(q) plane-quartic bound does
not imply an improvement over elliptic rho on the same field. A smaller
factor base with large-prime recombination, arbitrary full-Jacobian
target decomposition, extension-field descent, catalog promotion and
matched performance evaluation remain unimplemented. See the frozen
[protocol](PROTOCOL.md) for the acceptance and accounting boundary.
