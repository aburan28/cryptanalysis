# ECC2K-130 volcano descendants: hardness sweep

`sage sweep.sage` (SageMath 10.9, about 4 min on an M4 Pro) writes `results.json` and `descendants.csv`.

E0 is `y^2 + xy = x^3 + 1` over F_{2^131}, using the modulus `x^131 + x^13 + x^2 + x + 1`. Every invariant below is independent of the basis.
Z[π] has conductor `f = 263 · P`, where `P = 146505763881528721` is prime. The volcano therefore has four levels, `O_c = Z + c·O_K` for c | f.

| Level | Disc | h(O_c) | Smallest noninteger degree | τ ∈ End | Instantiated |
|---|---|---|---|---|---|
| c = 1 (crater) | −7 | 1 | 2 | yes | E0 |
| c = 263 | −484183 | 262 | 121046 | no | **all 262** |
| c = P | −7P² | P+1 ≈ 2^57.02 | (1+7P²)/4 | no | algebraic only |
| c = 263P (floor) | −7f² | 262(P+1) ≈ 2^65.06 | (1+7f²)/4 | no | algebraic only |

`(−7|263) = +1`: 263 splits, giving 2 horizontal kernels and 262 descending ones. `(−7|P) = −1`: P is inert, so all P+1 P-isogenies from E0 descend.
To build the P and 263P levels you need isogenies of degree P ≈ 2^57, which is out of reach. Their hardness rows follow from the shared invariants below.

## Exhaustive 263 sweep (264 kernels)

The script works on the twist, where `E0t(F_q)[263] = (Z/263)²`. It computes a Vélu isogeny for each of the 264 kernel lines, then returns to trace t.

- 2 kernels are horizontal and give j = 1, i.e. back to E0. The other 262 descend.
- The 262 descendants have 262 distinct j-invariants, in 2 Frobenius (j ↦ j²) orbits of 131 each. None has j ∈ F_2.
- All 262 are `y^2 + xy = x^3 + b` (a = 0), and each has #E = 4N.
- 263-structure: the twist of every descendant has a cyclic `Z/263²` part, while the crater has `(Z/263)²`. This confirms End = O_263 for each one.
- GHS/Weil descent magic number: E0 has m(b) = 1, and **all 262 descendants have m(b) = 131**. Descent to F_2 would give genus ≈ 2^130, so no descendant is weak to GHS.
- DLP transfer: for each descendant, the script builds the F_q-rational 263-isogeny E0 → E_d from the same kernel polynomial (the char-2 twist fixes x). It maps a point of order N to a point of order N. **Verified for 262/262.**

## Shared invariants (identical for every curve in the isogeny class)

| Quantity | Value |
|---|---|
| #E | 4 · N, N prime (130 bits) |
| Trace | −22283658519494248867 |
| Embedding degree | 216464610000596986937760855436835237 (118 bits), so MOV/FR is infeasible |
| Anomalous / supersingular | no / no |
| Twist order | 2 · 263² · (114-bit prime) |
| Rho, negation only | 2^64.33 iterations |
| Rho, negation + τ (131-orbit) | 2^60.81 iterations |

## Conclusion

No descendant, at any level, is weaker than E0.
On a descendant, native rho is harder (2^64.33) because τ is lost, and GHS gets worse (m goes from 1 to 131). MOV, anomalous and the twist are unchanged.
The ECDLP on each descendant is equivalent to the ECDLP on E0, since one degree-263 isogeny evaluation connects them (verified explicitly on the 263 level). The class's effective hardness is therefore E0's 2^60.81.
The only per-curve differences are the coefficient b, which feeds into summation-polynomial and Gröbner presentations, and End. Neither changes the group.
