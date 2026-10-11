# Normal-basis barrel-shift front end for implicit W24/m5

The parent [seed-plus-exponent gate](../ecc2k130-orbit-closed-w24-seed-20261006/RESULT.md)
verified exact membership and group encoding for the source Koblitz curve,
but a solver still needs to select an unknown exponent for each summand.
Enumerating all 131 Frobenius images per leaf creates 655 leaf alternatives
in an m5 relation. This experiment tests a specific circuit representation:
convert a 24-bit W24 seed into a 131-bit **normal-basis** word, then apply a
cyclic conditional barrel rotation for an 8-bit exponent in `0..130`.
Frobenius is a rotation in that basis. The circuit front end is compared to
the exact polynomial-field Frobenius on frozen inputs; no PDP solver is run.

`CONFIG.json` pins the parent PR head and source/result hashes, deterministic
normal-element search law, the eight rotation layers, all 56 positive and
64 negative parent field words, and ten control exponents including 127,
128, 129 and 130. A normal element is the first nonzero SHA-derived field
word whose 131 successive squares are linearly independent over `F₂`.
The producer will archive its exact polynomial↔normal conversion matrices
and their hashes. The eight layers conditionally rotate by `1,2,4,8,16,32,
64,128` positions modulo 131; exponents outside `0..130` must be rejected.

For every frozen field word, verify both conversion directions. For each of
the ten control exponents, require the barrel output converted to polynomial
form to equal direct `2^k`-powering. The 56 planted positive rows must also
match the parent `orbit_x` at their original exponents. A checked-Sage
verifier will independently reconstruct the normal element, normal-orbit
rank, conversion, and all rotation equalities using Sage field arithmetic
and binary linear algebra. Tests must include a wrong rotation and an
out-of-range exponent rejection. Preserve all failed controls.

The gate ledger must count, per summand, every conditional mux in the eight
131-bit layers and every XOR in the actual W24-seed→normal and
normal→polynomial linear maps. Report five-leaf totals, and separately
state that exponent-range constraints, rationality, Semaev/PDP equations,
solver search, relation collection, final matrix and target recovery are
**excluded**. A mux can be implemented as one AND plus two XOR gates;
report those equivalent counts only as circuit structure, not measured SAT,
F4/F5 or wall-time performance. The 4-GiB/120-s producer and 4-GiB/180-s
Sage limits are stop rules. Any local Sage command uses the checked
`/Volumes/SSD990/cryptanalysis/sage` launcher and saves `--runtime-info`
before the verifier.

This is a follow-up representation gate stacked on the parent PR. It has no
ordinary PDP query, rank, scalar recovery or rho comparison; `candidate_id`
and all end-to-end costs remain `null`. If the front end passes, the next
experiment must attach it to a complete bounded m5 Semaev/Boolean solver
and first find a planted **unknown** witness. Only then may an ordinary
query stream be frozen to estimate natural yield and useful rank.
