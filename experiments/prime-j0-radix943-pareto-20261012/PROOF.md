# Proof map for canonical radix-943 Pareto multiplication

The format represents a reduced secp256k1 scalar by a short Eisenstein
pair `(a,b)`. Its thirteen radix-943 digits reconstruct that pair exactly.
The corresponding affine table points are summed by a gauge-aware Pareto
tree. The inherited group theorem proves that changing gauges and tree
order preserves the leaf sum; the inherited cost theorem gives the modeled
ordinary-path field-product count of that tree.

For each coordinate the recoder maintains the integer equation
`stateᵢ = digitᵢ + 943 stateᵢ₊₁`. Repeated substitution yields
`state₀ = Σᵢ digitᵢ 943ⁱ + 943¹³ state₁₃`. The Rust function asserts
`state₁₃ = 0` for both coordinates. `Recoding.lean` proves this
reconstruction for arbitrary signed digits and a zero terminal state, so
the actual digit values and their signs require no special case in the
induction.

| Result | Lean declaration or evidence | Assumptions and scope | Status |
| --- | --- | --- | --- |
| Exact signed radix reconstruction | `PrimeJ0Radix943Recoding.reconstruct`, `reconstruct_pair` | Every quotient/digit step obeys the stated integer equation; both final coordinates are zero | Checked with Lean 4.34.1 |
| Gauge tree represents the selected table-point sum | `PrimeJ0GaugeTree.reordered_tree_correct` in `../prime-j0-gauge-tree-20261012/GaugeTree.lean` | Abelian point group, order-three additive automorphism, each selected term used once | Checked in inherited module |
| Ordinary-path tree cost `10n−14 + rotations` and pruning | `PrimeJ0ParetoCost.joinedTree_cost`, `dominatedSubtree_replacement` in `../prime-j0-pareto-tree-20261012/ParetoCost.lean` | Affine leaves; joins cost 6, 10, 14 products; each rotation costs one; additive work and max-plus depth | Checked in inherited module |
| All reduced scalar representatives terminate in thirteen digits | Integer covering-radius certificate and residue enumeration in `../prime-j0-secp256k1-native/radix943-screen-result.json` | Secp256k1 scalar lattice, radix 943, nearest residue-class Eisenstein digits | Mathematical certificate and finite check; Lean formalization open |
| Rust table and curve arithmetic realize those group terms | Release 4,096-case design panel, 512-case independently generated holdout, 129-case fixture | Concrete fixed-base secp256k1 implementation | Point replay checked; Lean refinement theorem open |

The remaining Lean obligation is a definition of the secp256k1 scalar
lattice and Eisenstein norm, a proof of the nearest-representative and
digit covering bounds implying zero terminal state, and a refinement from
the Rust atlas, table entries, and exceptional XYZZ branches to the group
theorem. The current Lean reconstruction theorem takes the exact per-step
equations and zero terminal state as hypotheses; it does not assume the
desired reconstruction conclusion. The earlier finite Pareto-plan decoder
and search-to-Rust refinement obligation also remains open.

The toolchain is pinned in `lean-toolchain`. `lean-build.txt` records the
three actual module builds and all `#print axioms` outputs. These modules
contain no `sorry`, `admit`, custom mathematical axiom, or native-evaluation
bypass. The reported standard foundations are `propext` and `Quot.sound`.
`lean4checker --fresh` is unavailable on this host.
