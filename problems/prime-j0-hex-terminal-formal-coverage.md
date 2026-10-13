# Fixed-width chooser and terminal census formal coverage

- **Status:** `investigating`
- **Kind:** proof gap (word-level implementation bridge and finite census)
- **Affected work:** [Voronoi terminal proof](../experiments/prime-j0-hex-terminal-20261012/PROOF.md), [PR #837](https://github.com/aburan28/cryptanalysis/pull/837), `PrimeJ0HexTerminal.recoded_terminal_in_domain`
- **Next action owner:** scalar-format implementer
- **Last updated:** 2026-10-12

## Problem

The opt-in secp256k1 radix-256 evaluator has a checked conditional terminal-domain theorem, but its production fixed-width chooser has not yet been proved in Lean to satisfy the theorem's six-neighbor hypothesis for every reduced 256-bit scalar. The exact 66,133-pair/11,023-orbit terminal census also has an executable integer audit but no Lean cardinality theorem.

The instance is the secp256k1 prime-order subgroup with the `U,V,W` Eisenstein kernel lattice in `experiments/prime-j0-hex-terminal-20261012/search.json`. The native path is `hexagonal_certified_fixed_choice_words` in `experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs`, followed by fifteen radix-256 digit recodes and the table in `hex_terminal.rs`. A full formal coverage claim needs to connect that exact word-level choice, including its fallback, to `sixNeighborsClosest` and the enumerated table domain.

## Evidence and uncertainty

- **Observed:** `check.py --check` builds and axiom-audits the four-corner geometry, Cauchy support, reconstruction, and conditional terminal theorem under Lean 4.34.1. `search.py --check` exhaustively enumerates the bounded integer domain. `screen.py --check` covers 4,096 design and 1,536 earlier holdout scalars; `replay.json` covers four independent 512-case point panels, including a source-frozen holdout. The same semantic replay passed in an offline Linux ARM64 container. Each check has the scope stated here; none ranges over all subgroup scalars.
- **Derived or proved:** `four_corner_minimum_has_hex_strips` proves the exact cell-score minimum obeys all three Voronoi strip bounds for every normalized cell coordinate. `reciprocal_high_fraction_interval` derives the two-unit high-fraction enclosure from a floor-reciprocal inequality and exact product-limb decomposition for arbitrary integers. `fraction_limb_score_intervals` proves the Rust classifier's score ranges from that enclosure, and `strictly_separated_interval_certifies_minimum` proves strict range separation selects a minimum. `recoded_terminal_in_domain` proves terminal inclusion when the initial representative satisfies `sixNeighborsClosest` and the prior digit/norm bounds. The exact reciprocal quotient argument is documented in `experiments/prime-j0-exact-reciprocal-20261010/PROTOCOL.md`; its integration with the native limb product is not a Lean theorem here.
- **Suspected explanation:** no mathematical failure is known. The missing steps are formal definitions and proofs for the 512-bit product/high-limb interval classifier and a checkable finite count certificate.
- **Missing capability:** Lean model and proof that the native fixed reciprocal constants satisfy the floor bound and that `reciprocal_cell_limbs_from_words_512` supplies the exact product decomposition used by the new interval theorem, plus composition of the certified and fallback branches with the four-corner minimum; Lean cardinality proof for the sector rows.
- **What this evidence does not establish:** sampled scalar replays and a Python/Rust enumeration do not prove all-scalar word-level coverage or a kernel-checked finite census. The conditional theorem must retain its hypothesis until the bridge is checked.

## What would unblock it

- [ ] For every `k : Nat` with `k < r`, prove that the exact seven-limb constants and 512-bit product produce the two cell quotients and that either the interval classifier's chosen corner minimizes all four exact scores or the fallback chooses such a minimum. Prove the resulting pair satisfies `sixNeighborsClosest`; build the actual module with pinned Lean and audit `#print axioms` without `sorry`, `admit`, custom claim axioms, or unverified native evaluation.
- [ ] Prove in Lean that the integer pairs satisfying `3N(t)≤66051` and the three `hexLimit` strips form exactly 66,133 pairs and 11,023 unit orbits, with contiguous canonical rows matching the native table. A certificate of row endpoints may replace brute-force reduction only if Lean checks each endpoint, exclusion, count, and orbit property from exact definitions.

The first condition would close the all-scalar inclusion proof. The second would formally certify the table's exact size and indexing. Both are needed for a full formal coverage statement; they do not establish a CPU speedup or host isolation.

## Next discriminating step

- **Action or proof obligation:** prove the fixed seven-limb reciprocal constants satisfy the floor inequality and the 512-bit word product yields the exact decomposition required by `reciprocal_high_fraction_interval`; compose its enclosure with the checked classifier separation lemma and model the exact fallback separately.
- **Inputs and controls:** use the frozen reciprocal constants and subgroup order in `eisenstein_fixed.rs`, the exact quotient statement in `prime-j0-exact-reciprocal-20261010/PROTOCOL.md`, and the current `VoronoiTerminal.lean`. Keep the native 4,096+2,048 scalar panel as an implementation control, not as the universal proof.
- **Execution limits and stop condition:** symbolic proof must cover all `0≤k<r`; stop and preserve a counterexample if any interval bound or limb identity fails. Do not expand sampled panels as a substitute for the quantified proof.
- **Outcomes and next actions:** a checked limb interval lemma moves to composing the full chooser theorem; a counterexample requires fixing the chooser and replaying the frozen panels; a missing Lean arithmetic lemma remains a named proof obligation with its exact failed goal.
- **Recheck trigger:** a change to the reciprocal constants, limb product, classifier, fallback, terminal domain, or Lean proof.

## Resolution and history

- 2026-10-12: opened after PR #837 review identified the unlinked proof and census gaps. The four-corner cell geometry and conditional terminal theorem were already checked; the word-level and cardinality bridges remain open.
- 2026-10-12: Lean checked the score intervals implied by a two-unit high-fraction coordinate range and the generic strict-separation implication. The native limb-product-to-interval bridge remains open.
- 2026-10-12: Lean checked the reciprocal-inequality/product-decomposition implication to the two-unit coordinate enclosure. The word-level product identity, fixed constants, fallback, and census bridges remain open.

Unresolved.
