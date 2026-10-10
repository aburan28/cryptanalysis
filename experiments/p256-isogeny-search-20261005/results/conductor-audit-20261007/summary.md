# P-256 retained-registry conductor audit

## Result

Every one of the 2,226 retained curves has endomorphism-ring conductor `1` in
the maximal order. Every explicit isogeny path remains at volcano level zero.
The audit classified all 26,162 stored path-edge occurrences, representing
2,225 unique directed edges, as horizontal; it found zero vertical edges and
zero curves with a nontrivial or unknown conductor.

This is an exact algebraic conclusion, not an empirical timing result and not
2,226 independent black-box endomorphism-ring computations.

## Certificate chain

For the common P-256 isogeny class,

```text
t = p + 1 - n
  = 89188191154553853111372247798585809583

D_pi = t^2 - 4p
     = -455213823400003756884736869668539463648899917731097708475249543966132856781915
```

The repository verifies the complete squarefree prime factorization

```text
|D_pi| =
  3
  * 5
  * 456597257999
  * 1428624589419343516204097
  * 46523541035814968339936406074986559003387.
```

Primality is checked by recursive Pocklington certificates with deterministic
64-bit leaves. The squarefree discriminant is `1 mod 4`, hence fundamental.
Therefore the Frobenius order is already maximal:

```text
Z[pi] = O_K.
```

For every ordinary curve `E` in the class,

```text
Z[pi] subseteq End(E) subseteq O_K.
```

The endpoints coincide, so `End(E) = O_K` and
`f_End(E) = [O_K : End(E)] = 1`. Thus
`v_l(f_End(E)) = v_l(1) = 0` for every rational prime `l`.

## What was checked per curve

The deterministic replay reconstructed the retained union from fourteen frozen
candidate registries. For each candidate row it checked:

- the same field modulus `p` and group order `n`;
- the recomputed trace `t` and discriminant `D_pi`;
- continuity of the explicit path and its final `j`-invariant;
- conductor `1`, possible-order count `1`, and the exact order discriminant;
- level zero for every prime degree appearing in its path; and
- level-zero endpoints and horizontal orientation for every stored path edge.

The curve-specific `End(E)` field is therefore marked `proved_exactly` by a
`class-wide order squeeze`. It is also marked as **not** an independent
curve-specific endomorphism-ring computation. That distinction prevents a
derived certificate from being misreported as a measurement.

## Scope and attack relevance

An isogeny itself does not have an endomorphism conductor; its domain and
codomain do. Here every endpoint has conductor `1`, so all retained edges are
horizontal. There is no volcano floor or lower level whose different
endomorphism order could supply exceptional structure.

This conclusion is class-wide even though the explicit registry is bounded to
2,226 curves, depth 17 for degrees `3,5,11,13`, and one-hop prime degrees
through 199. It does **not** enumerate the full class group, measure rho speed,
or establish an ECDLP speedup. It eliminates conductor variation and vertical
volcano descent as candidate sources of a speedup.

Discovery and certificate verification are reusable precomputation. This audit
adds no per-key attack measurement and no per-key isogeny-mapping cost.

## Reproduction

```bash
python3 scripts/audit_retained_conductors.py \
  --output results/conductor-audit-20261007/audit.json
python3 scripts/verify_retained_conductor_audit.py
```

The machine-readable audit contains one row per retained curve, each path's
degree sequence, occurrence counts, and one classification row per unique
directed path edge. `receipt-conductor-audit-20261007.json` binds the source
manifest and frozen artifacts.

## Primary sources

- Waterhouse, [*Abelian varieties over finite fields*](https://www.numdam.org/item/ASENS_1969_4_2_4_521_0/), for the endomorphism-order classification.
- Sutherland, [*Isogeny volcanoes*](https://doi.org/10.2140/obs.2013.1.507), for volcano levels and horizontal/vertical terminology.
