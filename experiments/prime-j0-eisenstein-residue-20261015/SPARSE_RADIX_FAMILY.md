# A sparse Eisenstein radix family

The family `πₖ=(2ᵏ−1)+2ᵏτ`, with `τ²=3τ−3`, keeps the short point action `πₖP=[2ᵏ](P+τP)−P` while changing the digit-table size and recoding length. Its exact norm is `Nₖ=7·2²ᵏ−5·2ᵏ+1`, and the cyclic quotient has the explicit residue `τ↦4−7·2ᵏ` modulo `Nₖ`. These identities give a concrete design space around the measured `k=7` radix, including smaller tables that may improve one-scalar cold cost.

## Algebra and proof map

For an arbitrary integer `t`, define `πₜ=(t−1)+tτ`. Multiplication on an integer pair is

`πₜ(u,v)=((t−1)u−3tv, tu+(4t−1)v)`.

The [pinned Lean 4.34.1 module](SparseRadixFamily.lean) checks five results: `family_shortcut` proves the `[t](1+τ)−1` action; `family_norm` proves `N(πₜ)=7t²−5t+1`; `family_residue` proves `(t−1)+t(4−7t)=−N(πₜ)`; `family_residue_polynomial` proves the quotient root satisfies `s²−3s+3=7N(πₜ)` for `s=4−7t`; and `family_norm_scaling` proves `N(πₜz)=N(πₜ)N(z)` for every integer pair `z`. The [fresh checker](check_sparse_radix_family_lean.py) and [receipt](sparse-radix-family-lean-check.json) retain the source hashes, actual successful builds, and `#print axioms` for each declaration. The proofs use the standard Lean foundations `propext`, `Classical.choice`, and `Quot.sound`.

## Exact recoding screen

The [integer screen](screen_sparse_radix_family.py) uses one frozen 12,288-scalar fixture, the same short-lattice selector, signed quotient residues, and exact integer division at every radix step. It independently reconstructs every original scalar pair from the selected digits and terminal pair. The fixture SHA-256 is `a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3`; the [receipt](sparse-radix-family-screen.json) retains each digit and terminal digest. The displayed step is the first count at which every fixture terminal pair has norm below 5,000 and both coordinates at most 100 in absolute value.

| `k` | Radix pair | Norm | Orbit-folded digit seeds | Fixture steps | Maximum terminal norm |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | `(31,32)` | 7,009 | 1,169 | 20 | 1 |
| 6 | `(63,64)` | 28,353 | 4,727 | 17 | 9 |
| 7 | `(127,128)` | 114,049 | 19,009 | 15 | 7 |

The `k=7` row reproduces the existing sparse-radix screen's 19,009 digit seeds, 15 steps, and maximum observed terminal norm 7. The selected step counts are exact for this fixture; a global termination and selector bound for `k=5` or `k=6` remains a separate proof obligation. The next native gate is a hash-guarded `k=6` implementation with all frozen point outputs replayed, followed by matched Tier 1 one-scalar cold and prepared-table panels. The 4,727-seed table is the promising intermediate size to test first.
