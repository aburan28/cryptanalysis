# Complete radix-943 scalar recoding proof

The exact four-corner secp256k1 lattice and radix-943 choosers have a
checked Lean proof that **every integer scalar** obtains a representative
with `3Q(z)≤n`, thirteen digits with `3Q(d)≤943²`, a zero terminal
pair, and a digit sum congruent to the original scalar modulo the
subgroup order. The quotient equation is exact at every window.

The proof uses a hexagonal norm cell in transformed `(a+b,−b)`
coordinates. Three of its four translated copies suffice on each
triangular half of the `943×943` residue square. The chooser takes the
least `(Q(d),d₁,d₂)` among those four corners, preserving the bound.
The same cover, applied at the lattice determinant `n`, proves the
initial representative bound. Exact basis and endomorphism-kernel
integer certificates establish scalar congruence.
`PROOF.md` gives the written argument and maps each result to its Lean
declaration. `lean-build.txt` retains the pinned build and axiom audit;
`fixtures.json` and `scalar-fixtures.json` record 42 digit and 12 full
scalar cross-language replays.

| Item | Exact condition or result |
| --- | --- |
| Curve and subgroup | secp256k1; `n=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141` |
| Radix and window count | `R=943`, 13 windows |
| Norm | `Q(a,b)=a²+3ab+3b²` |
| Digit bound | `3Q(d)≤943²` for every chooser input |
| Step identity | `z=d+943q` for every chooser input |
| Initial representative bound | `3Q(nearestRepresentative(k))≤n` for every integer `k` |
| Termination | `(recode 13 (nearestRepresentative k)).2=(0,0)` for every integer `k` |
| Scalar congruence | The thirteen-digit sum maps to `k` modulo `n` under `a+λb` |
| Lean toolchain | `leanprover/lean4:v4.34.1` |
| Cross-language controls | 42/42 digit outputs and 12/12 complete scalar recodings match Python; 42/42 quotient equations checked |

The Rust word/orbit/curve implementation link remains an open Lean
refinement. The existing format-174 operation-count and independent
point replays remain the implementation evidence. Complete-operation
CPU timing remains governed by
the host-isolation gate in `../../docs/ISOLATED_BENCHMARKS.md`.
