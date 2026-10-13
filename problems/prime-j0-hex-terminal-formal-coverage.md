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
- **Derived or proved:** `four_corner_minimum_has_hex_strips` proves the exact cell-score minimum obeys all three Voronoi strip bounds for every normalized cell coordinate. `native_reciprocals_floor` checks the two copied seven-word constants against exact floor inequalities, and `reduced_scalar_below_fraction_tail` checks the scalar-range premise. `exact_product_high_fraction_decomposition` splits an exact product into the high quotient, high fractional word, and bounded low remainder. `fraction_base_width` and `schoolbook_muladd_fits_double_word` certify that an inner multiply-add with 64-bit words and carry fits in `u128`. `schoolbook_word_step` proves the low-word/carry update preserves weighted value; `schoolbook_pass_value` and `schoolbook_pass_bounds` extend this across any finite list of reciprocal words, retaining 64-bit bounds. `carry_pass_value`, `carry_pass_zero`, and `carry_pass_bounds` prove exact trailing carry propagation and its early-stop condition. `schoolbook_whole_pass_value` and `shifted_schoolbook_pass_value` compose a modeled outer iteration across an unchanged prefix, reciprocal words, and suffix, with length and bound results. `schoolbook_outer_at_value` matches the native indexed slice, and `four_scalar_word_product` composes the four exact increments under explicit zero-carry premises. `reciprocal_high_fraction_interval` derives the two-unit high-fraction enclosure from a floor-reciprocal inequality and exact product-limb decomposition for arbitrary integers. `fraction_limb_score_intervals` proves the Rust classifier's score ranges from that enclosure, and `strictly_separated_interval_certifies_minimum` proves strict range separation selects a minimum. `recoded_terminal_in_domain` proves terminal inclusion when the initial representative satisfies `sixNeighborsClosest` and the prior digit/norm bounds. The exact reciprocal quotient argument is documented in `experiments/prime-j0-exact-reciprocal-20261010/PROTOCOL.md`; its integration with the native limb product is not a Lean theorem here.
- **Suspected explanation:** no mathematical failure is known. The missing steps are formal definitions and proofs for the 512-bit product/high-limb interval classifier and a checkable finite count certificate.
- **Missing capability:** Lean proof that each of the four indexed eleven-word array passes has zero final overflow carry, and proof that the returned three high words and fractional word match `exact_product_high_fraction_decomposition`. `schoolbook_outer_at_value` checks the offset and reciprocal-sized slice for one pass; `four_scalar_word_product` composes all four increments conditional on those zero carries. Composition of certified and fallback branches with the four-corner minimum and Lean cardinality proof for the sector rows remain open. Synchronization of copied Lean reciprocal words with the native source is checked by `check.py`.
- **What this evidence does not establish:** sampled scalar replays and a Python/Rust enumeration do not prove all-scalar word-level coverage or a kernel-checked finite census. The conditional theorem must retain its hypothesis until the bridge is checked.

## What would unblock it

- [ ] For every `k : Nat` with `k < r`, prove that the exact seven-limb constants and 512-bit product produce the two cell quotients and that either the interval classifier's chosen corner minimizes all four exact scores or the fallback chooses such a minimum. Prove the resulting pair satisfies `sixNeighborsClosest`; build the actual module with pinned Lean and audit `#print axioms` without `sorry`, `admit`, custom claim axioms, or unverified native evaluation.
- [ ] Prove in Lean that the integer pairs satisfying `3N(t)≤66051` and the three `hexLimit` strips form exactly 66,133 pairs and 11,023 unit orbits, with contiguous canonical rows matching the native table. A certificate of row endpoints may replace brute-force reduction only if Lean checks each endpoint, exclusion, count, and orbit property from exact definitions.

The first condition would close the all-scalar inclusion proof. The second would formally certify the table's exact size and indexing. Both are needed for a full formal coverage statement; they do not establish a CPU speedup or host isolation.

## Next discriminating step

- **Action or proof obligation:** discharge the four zero-carry premises of `four_scalar_word_product` from bounded input words and the eleven-word product capacity, then identify output indices `8..10` and `7` with the exact quotient and high fractional word. Compose the resulting enclosure with classifier separation and model the exact fallback separately.
- **Inputs and controls:** use the frozen reciprocal constants and subgroup order in `eisenstein_fixed.rs`, the exact quotient statement in `prime-j0-exact-reciprocal-20261010/PROTOCOL.md`, and the current `VoronoiTerminal.lean`. Keep the native 4,096+2,048 scalar panel as an implementation control, not as the universal proof.
- **Execution limits and stop condition:** symbolic proof must cover all `0≤k<r`; stop and preserve a counterexample if any interval bound or limb identity fails. Do not expand sampled panels as a substitute for the quantified proof.
- **Outcomes and next actions:** a checked limb interval lemma moves to composing the full chooser theorem; a counterexample requires fixing the chooser and replaying the frozen panels; a missing Lean arithmetic lemma remains a named proof obligation with its exact failed goal.
- **Recheck trigger:** a change to the reciprocal constants, limb product, classifier, fallback, terminal domain, or Lean proof.

## Resolution and history

- 2026-10-12: opened after PR #837 review identified the unlinked proof and census gaps. The four-corner cell geometry and conditional terminal theorem were already checked; the word-level and cardinality bridges remain open.
- 2026-10-12: Lean checked the score intervals implied by a two-unit high-fraction coordinate range and the generic strict-separation implication. The native limb-product-to-interval bridge remains open.
- 2026-10-12: Lean checked the reciprocal-inequality/product-decomposition implication to the two-unit coordinate enclosure. The word-level product identity, fixed constants, fallback, and census bridges remain open.
- 2026-10-12: Lean checked the copied native reciprocal constants against both floor inequalities and checked that every reduced scalar is below the 448-bit fractional tail. Word-product, fallback, and census bridges remain open.
- 2026-10-12: Lean checked extraction and remainder bounds for an exact integer product, plus the 64-to-128-bit inner multiply-add bound under an incoming 64-bit carry. The native loop invariant remains open.
- 2026-10-12: Lean checked a modeled inner word step and a full arbitrary-length pass, including weighted-value and 64-bit bounds. The shifted outer-array and carry-propagation link remains open.
- 2026-10-12: Lean checked trailing carry propagation, its zero-carry early stop, and a complete shifted outer pass over arbitrary prefix, reciprocal words, and suffix. Four-iteration native-array composition and returned-word identification remain open.
- 2026-10-12: Lean checked one native-indexed outer pass using `take`, `drop`, and `zip`, including exact positional value and fixed array length. Four-pass composition, overflow exclusion, and returned-word identification remain open.
- 2026-10-12: Lean checked composition of four indexed passes into the exact four-word scalar times the seven-word reciprocal under explicit zero-carry premises. Overflow exclusion and returned-word identification remain open.

Unresolved.
