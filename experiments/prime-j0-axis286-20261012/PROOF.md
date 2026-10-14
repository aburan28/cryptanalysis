# Proof map for the fourteen-window radix-286 format

The same certified secp256k1 Eisenstein representative is recoded in
fourteen radix-286 steps. The full representative and every ordinary digit
obey the norm hypotheses below. The terminal pair is factored as two axis
digits after a unique six-unit sector rotation.

| Mathematical result | Lean declaration | Exact hypotheses and status |
| --- | --- | --- |
| Bounded nearest residue digit | `PrimeJ0Axis286DigitCover.nearest_digit_bound` | Any integer coordinate pair; radix 286; checked |
| Fourteen-step scalar reconstruction and subgroup congruence | `PrimeJ0Axis286DigitCover.scalar_recode_reconstruct`, `scalar_recode_congruence` | Reduced secp256k1 scalar and the pinned lattice representative; checked |
| Uniform terminal norm bound | `PrimeJ0Axis286DigitCover.scalar_top_bound` | `3·norm(representative) ≤ subgroupOrder`; cap `192971294`; checked |
| Unique sector and two-axis terminal factorization | `PrimeJ0Axis286TopRank.unique_sector_image`, `axis_factorization` | Nonzero terminal pair under that cap; `1 ≤ u ≤ 16040`, `1 ≤ b ≤ 10693`; checked |
| Radix-286 point-entry minimum among fourteen-window integer radices | `search.py` exact census and tail argument | Written proof and exhaustive integer receipt; Lean finite Burnside/census bridge remains open |

The exact point-entry formula for radix `B ≥ 2` is

`14·(B² + gcd(2,B)² + 2·gcd(3,B) + 2)/6 + u_max(B) + b_max(B)`,

where `u_max(B) = floor(sqrt(4·cap(B)/3))`,
`b_max(B) = floor((2u_max(B)-1)/3)`, and
`cap(B) = floor((2^128 + B + ··· + B^14)²/B^28)`.
The six-unit orbit count follows Burnside's lemma, including fixed
residues. For `B ≤ 245`, the exact radius ratio decreases with `B`,
so the terminal axes have at least 233,256 entries, already above
217,609. For `B ≥ 306`, ordinary tables alone have at least
`14·306²/6 = 218,484` entries. `search.py` checks every radix 245
through 306; radix 286 has 217,609 entries and the runner-up, radix
285, has 217,622. The stated global minimum is an exact integer
census with a written tail proof; its Lean formalization is partial
until the Burnside count, tail monotonicity, and finite interval
comparison are connected in one declaration.

`check.py` builds the actual Lean modules under pinned Lean 4.34.1 and
audits each `#print axioms`. The receipt `lean-build.txt` contains the
source hashes and output. Only standard `propext`, `Classical.choice`,
and `Quot.sound` occur. There are no research axioms or admitted proofs.
The native builder and independent public-point replay provide the
implementation bridge; the Rust source transformation is not a Lean
refinement proof.
