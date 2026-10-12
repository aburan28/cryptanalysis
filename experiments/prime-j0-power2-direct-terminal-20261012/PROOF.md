# Proof map for the direct-terminal radix-256 format

The checked Lean modules use the exact secp256k1 subgroup order and the
nearest Eisenstein representative theorem from the pinned radix-919
dependency. They preserve the full scalar quantifier.

| Mathematical result | Lean declaration | Status |
| --- | --- | --- |
| Every integer pair has a bounded nearest radix-256 digit | `PrimeJ0Power2DirectTerminalDigitCover.nearest_digit_bound` | Checked |
| Fifteen-step reconstruction and scalar congruence | `scalar_recode_reconstruct`, `scalar_recode_congruence` | Checked |
| Uniform terminal cap `3N(t)≤66051` | `PrimeJ0Power2DirectTerminalDigitCover.scalar_top_bound` | Checked |
| Unique six-unit sector image | `PrimeJ0Power2DirectTerminalTopRank.unique_sector_image` | Checked |
| Every bounded top pair is zero or an image of one disk-table pair | `direct_terminal_table_covers` | Checked |
| Exact 13,314 terminal orbit count and contiguous row rank | `search.py` exhaustive integer census and rank audit | Lean finite-census/rank bridge open |

`check.py --check` builds `TopBound.lean`, `DigitCover.lean`, and
`TopRank.lean` under pinned Lean 4.34.1 after rebuilding the two imported
radix-919 modules. It audits every reported theorem with `#print axioms`;
the receipt is `lean-build.txt`. The checked proofs use only Lean's
standard `propext`, `Classical.choice`, and `Quot.sound`. The terminal
coverage theorem proves that an element of the declared disk domain
exists for every recoded scalar; `search.py` independently checks that
the generated row index enumerates that exact domain. Connecting the
finite row implementation and its exact count to Lean remains open.

The native Rust evaluator and its atlas audit are recorded in
`direct_terminal.rs`. All three 512-scalar panels in `replay.json` compare every
complete point with the radix-286 evaluator and independently generated
points on macOS ARM64 and Linux ARM64. These are implementation checks;
the Lean modules prove the mathematical scalar identity and
terminal-domain reachability, while the finite row rank bridge remains
open.
