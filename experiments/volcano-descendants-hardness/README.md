# ECC2K-130 volcano descendants: hardness sweep

Run this script through the repository's checked `./sage` launcher (SageMath
10.9; the historical run took about 4 min on an M4 Pro). It writes
`results.json` and `descendants.csv` in its working directory; use a fresh run
directory to preserve the historical outputs.

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

## Conductor-aware navigation metadata

New runs attach `conductor_navigation` and a `navigation` record to each
order-stratum row. `conductor_navigation.py` can also annotate a historical
summary into a **new file**, without executing Sage or any curve construction:

```sh
python3 experiments/volcano-descendants-hardness/conductor_navigation.py \
  --input experiments/volcano-descendants-hardness/results.json \
  --sweep-summary --allowed-primes 263 --output /tmp/conductor-navigation.json
python3 -m unittest discover -s experiments/volcano-descendants-hardness \
  -p test_conductor_navigation.py -v
```

The Sage sweep accepts `--navigation-primes 263` (default). This option
describes the allowed degrees for the metadata analysis; it does not change
the existing degree-263 construction loop or launch additional searches.

The inventory validates `t² − 4q = f_pi² D_K`, a negative fundamental
discriminant, ordinary applicability, a complete conductor factorization,
and characteristic-compatible allowed prime degrees. It enumerates all divisor
orders, retaining their discriminants, prime-specific levels, excluded-prime
barriers, and restricted order-component keys. Empty allowed-prime lists are
supported. Supersingular inputs and characteristic-prime volcano labels are
rejected. Limits are explicit: deterministic prime checks cover factors below
`2^64`, the exact fundamental-discriminant check covers squarefree parts up to
`10^8`, and enumeration defaults to at most 4096 strata. Unsupported inputs
raise errors rather than becoming guessed facts or silently partial results.

| Conductor stratum | Separation from source order `f_E = 1`, allowed degree 263 |
|---|---|
| 1 | No conductor obstruction |
| 263 | No conductor obstruction |
| P | Excluded prime P must change valuation |
| 263P | Excluded prime P must change valuation |

Here `P = 146505763881528721`. Its degree needs 58 bits to encode; this is
**not** a `2^58` work estimate. A component key fixes valuations at excluded
primes. Equal keys only remove this particular conductor obstruction; they
do not prove connectivity, fast navigation, or an available map between two
curves. Different keys separate order strata for walks whose prime degrees
belong to the declared set. This does not prove hardness for arbitrary
isogeny algorithms. A local volcano surface is maximal at its prime, and
need not be the globally maximal order.

The generic JSON input uses the `inventory` function's keyword fields:
`characteristic`, `q`, `trace`, `field_discriminant`,
`frobenius_conductor`, `factors` (prime strings to positive exponents), and
optional `source_conductor`, `source_evidence`, `max_strata`. Integers can be
decimal strings. An unknown source conductor remains null, with unknown
separation. A supplied source conductor needs an evidence reference and
must divide `f_pi`; the helper checks arithmetic consistency, not the proof
in that reference. The existing-summary adapter is specific to this -7
Koblitz class. Other classes use the generic invariant manifest interface.

Order strata have `curve_id: null`, `construction_status: not_constructed`,
`map_status: unknown`, and `measured_advantage: null`. These are hypothetical
orders, not fabricated curve-catalog entries. The parent historical level row
still retains its own `instantiated` flag. Attach exact EC1 identities and
verified maps only when concrete curves exist, following
[VOLCANO_NAMING.md](../ic-candidate-catalog/VOLCANO_NAMING.md).

This addition supplies the navigation inventory. It does **not** search for
exceptional relation geometry, construct P-degree neighbors, or establish
an advantage on the uninstantiated strata. The historical conclusion above
must not be used as a proof of equal DLP difficulty on those strata: the
verified degree-263 transfers cover the constructed degree-263 neighbors.
Conductor metadata alone proves neither equal nor different DLP cost.

The order/level relationship follows Andrew Sutherland,
[Isogeny volcanoes](https://msp.org/obs/2013/1-1/obs-v1-n1-p25-s.pdf),
Sections 2.7 and 2.11–2.12. This change performs metadata consistency checks,
not a new mathematical search or hardness measurement; historical graph and
measurement artifacts are unchanged.
