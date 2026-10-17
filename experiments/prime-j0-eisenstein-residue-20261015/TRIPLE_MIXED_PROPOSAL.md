# A 78-tripling mixed Eisenstein radix for joint secp256k1 multiplication

The mixed recurrence evaluates `aG+bQ` using two quotient steps in radix
`81+omega` (norm 6481) followed by fourteen in radix `243+omega` (norm
58807). Reverse Horner evaluation applies fourteen `243+omega` point steps
and then two `81+omega` steps. Their fixed operator count is
`14*5+2*4=78` j=0 triplings, sixteen rotations, and sixteen projective
additions. The existing fixed `81+omega` and `243+omega` recurrences each
use 80 triplings. Digit additions, Q-table construction, inversions, memory,
and conversion are separate costs and determine the eventual wall result.

## Uniform initial bound and terminal proof

In the certified scalar lattice, the basis vectors `W` and `V` satisfy
`Q(W)=Q(V)=Q(W+V)=n`, where `n` is the secp256k1 subgroup order and
`Q(a,b)=a²+3ab+3b²`. For floor-cell remainders `0≤x,y<n`, the floor
representative `(xW+yV)/n` has

```text
Q((xW+yV)/n) = (x²+y²−xy)/n ≤ n.
```

If `x≤y`, then `x²+y²−xy = y²−x(y−x) ≤ y² ≤ n²`; the other case is
symmetric. The native scalar reducer chooses the nearest of four corners,
including the floor corner, so its selected representative inherits this
bound when its certified corner decision matches the exact four-corner
minimum. The Lean theorem exposes that selector comparison as a hypothesis.

Each radix step uses the existing digit bound and weighted norm inequality
`100D Q(next) ≤ 101 Q(current)+10100D`. Starting from `Q(initial)≤n`, two
steps with `D=6481` followed by fourteen with `D=58807` give
`Q(terminal)≤647<5000`. The terminal uses the existing norm-5000 table.
The [Lean module](TripleMixedRadix.lean) proves the lattice geometry,
selected-corner implication, numeric recurrence, exact mixed quotient
terminal statement, and shared two-scalar point Horner composition. It
builds with pinned Lean 4.34.1; the [proof verifier](verify_triple_mixed_lean.py)
records the build and `#print axioms` output in
`triple-mixed-lean-check.json`. The quotient-ring-to-native signed-limb
refinement, reciprocal corner decision, and curve-operation refinement
remain explicit implementation proof obligations.

## Native implementation and replay

The opt-in [native recoder and evaluator](joint_mixed78.rs) reuse the
existing radix-81 and radix-243 digit selectors and the radix-243 Q-table
planner. The [command](rho_restart_joint_mixed78.rs) charges target Q-table
preparation and restart evaluation together. The
[hash-checked overlay](native_rho_restart_mixed78_overlay.py) adds the arm
after the pinned radix-81 and radix-243 overlays.

The local ARM64 release binary SHA-256 was
`f7f684d90314525f962668690e3a03387a6cec35724247c0016b20f89da8ec82`.
The [independent replay](triple-mixed-local-replay.json) verified 393 exact
point outputs over the frozen one- and 128-restart fixtures, alternate Q
points, 128 fresh seeded scalar pairs, and five edge cases. The first frozen
restart constructed 17 Q points; the 128-restart stream constructed 1,851.
Those figures identify the Q graph as a material part of the cost.

The archived parent source references eight temporary atlas binaries that
were absent from the local source archive. The first build failed on those
missing `include_bytes!` files. For this local correctness replay, the
missing files were supplied as empty diagnostic shims for modes outside this
path; that binary is not a complete reproducible benchmark artifact. The
replay receipt records this condition, and its elapsed fields are correctness
diagnostics only. A portable build must recover the real atlas bytes or
remove those unrelated modes through an audited source change, then freeze
the full source and Linux binary hashes.

## Decision gate

First compare the one-restart mixed path with the frozen `243+omega`,
`81+omega`, and OpenSSL arms on the same public point, charging Q preparation,
evaluation, and output conversion. Use the serial Tier 1 RunPod queue with
alternating pairs, exact replay, host counters, and bracketing A/A controls
under the [joint benchmark contract](RHO_JOINT_BENCHMARK_PLAN.md). The
128-restart stream asks the separate batch-amortization question. The two
saved triplings per restart become a measured improvement only if the full
charged interval passes that gate.
