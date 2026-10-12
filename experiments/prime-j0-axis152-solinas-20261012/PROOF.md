# Proof map for canonical radix-152 evaluation

The candidate selects the same secp256k1 group points as the merged
radix-152 XYZZ evaluator. It changes their field encoding from Montgomery
residues to canonical residues before table storage and uses the checked
Karatsuba Solinas field product in the point evaluator. The mathematical
scalar representation is unchanged.

| Result | Lean declaration and hypothesis | Verification |
| --- | --- | --- |
| Radix-152 scalar reconstruction, terminal axes, and unit-sector selection | `../prime-j0-axis152-20261012/PROOF.md`; exact secp256k1 order, pinned lattice basis, 16 radix-152 windows | Inherited checked modules and exact design census |
| Canonical secp256k1 field product and reduction | `../prime-j0-u14-solinas-20261012/PROOF.md`; canonical inputs below `p=2^256-2^32-977` | Inherited checked Lean reduction theorem |
| Nine-variable-product Karatsuba wide product | `../prime-j0-u14-karatsuba-20261012/PROOF.md`; integer limb identity before Solinas folds | Inherited checked Lean product identity |
| Ordinary-path 64-bit source-product saving | `PrimeJ0Axis152Solinas.ordinary_path_product_saving` in `Model.lean`; any natural addition and rotation counts, assuming source costs 360/160 per addition and 23/16 per rotation | Checked with Lean 4.34.1; `#print axioms` gives only `propext`, `Quot.sound` |

The model theorem gives the exact identity

`reference_products = candidate_products + 200·additions + 7·rotations`.

`model.py` binds the source files used to assign the per-operation constants
and applies that identity to the frozen replay counts. The source-level
bridge is the guarded transformation in `native_overlay_solinas.py` and the
two executed binaries. The Lean identities do not by themselves verify the
Rust limb implementation or the source-level branch count; the independent
point replay and boundary controls test those bridges. The source count
uses the ordinary nonexceptional addition path and includes the actual
nonzero rotations reported by the evaluator.

The pinned toolchain is in `lean-toolchain`; `lean-build.txt` retains the
actual build command, version, and axiom audit. No new group-theoretic
assumption is introduced by the field-encoding change.
