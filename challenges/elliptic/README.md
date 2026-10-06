# Elliptic-curve challenge corpus

A checked set of elliptic-curve discrete-log instances for the solvers in
this repository: Pollard rho (plain, negation-map, GLV, Frobenius),
Pohlig–Hellman, prime-field and j = 0 index calculus, Gaudry on
`E(F_{p^3})`, Koblitz / subfield index calculus, GHS Weil descent, MOV, the
Smart attack on anomalous curves, and walks on isogeny volcanoes.

The curves are not a copy of the standardised catalogue in
`suite/src/ecc/curve_zoo.rs`.  Each one is here because some structural
fact about it changes which algorithm is the fast one.

Field cardinalities run from `F_3` and `F_4` up to about 768 bits
(the largest field in the set has 771 bits).
Extension degrees are both prime and composite, in characteristics 2, 3
and odd primes.

## Layout

| file | role |
|---|---|
| `corpus.json` | the instances and the volcano graphs |
| `generate.py` | deterministic generator (`SEED = 20260922`). Re-run with `python3 challenges/elliptic/generate.py` |
| `c_registry.txt` | prime-field rows small enough for the 64-bit C solvers |

The suite loads the JSON from `cryptanalysis::ec_challenges`.

```sh
cd suite && cargo run --release -- ec-challenges summary
cargo run --release -- ec-challenges list --tag koblitz --max-bits 32
cargo run --release -- ec-challenges show --id pf-anomalous-b9
```

## Tiers

* **open** — group small enough to solve in a test.  The scalar is in the
  instance.  `pollard_rho_ecdlp` and `ca solve` can check themselves
  against it.
* **bench** — scalar published, group large enough that a run is a
  measurement.  Compare operation counts on two implementations of the
  same instance.
* **shape** — field at the top of the range (up to 768 bits).  Either a
  short public witness `[k]P`, so a new field implementation can check
  its group law, or a withheld scalar committed as
  `sha256(utf8(id + "\n" + decimal_scalar))`.  The group order is exact,
  from a point count or from the trace recurrence, so the cost of rho is
  known even when the log is not.

A relation checks as `[scalar]·base = target`.  On a prime field,
`ec_challenges::prime_curve` builds the `CurveParams` the existing rho
and index-calculus drivers take.

## What varies

| axis | where it shows up |
|---|---|
| j = 0, ordinary | `pf-j0-*`. Automorphism group of order 6. GLV rho, j = 0 index calculus |
| j = 1728, ordinary | `pf-j1728-*`. Automorphism group of order 4 |
| j neither | `pf-generic-*`. Negation is the only rational endomorphism |
| supersingular j = 0 or 1728 | `#E = p+1`, embedding degree 2. MOV, not GLV (`p` is in the wrong congruence class) |
| smooth supersingular | `pf-mov-*`. Pohlig–Hellman and MOV |
| anomalous `#E = p` | `pf-anomalous-*`. Smart–Semaev–Satoh–Araki |
| twist-insecure pair | `pf-twist-main-*` and `pf-twist-smooth-*`. The twist order is smooth |
| Koblitz `y² + xy = x³ + a x² + 1` | `bin-koblitz-a{0,1}-m*`, prime and composite `m`, including 61 and 768. Frobenius. Composite `m` is a GHS / Weil-descent shape; prime `m` is the case that descent does not apply to |
| proper binary subfield | `bin-subfield-k*-n*`, curve over `F_{2^k}` with `k > 1`, base-changed to `F_{2^n}` |
| characteristic 3 | `ter-*`. j = 0 model `y² = x³ + ax + b` and j ≠ 0 model `y² = x³ + ax² + b`. Prime and composite degrees, plus lifts to several hundred |
| odd extensions | `ext-p*-n*`. Degree 2, 3, 4, 5, 6, both subfield curves (Frobenius) and curves that do not descend to a proper subfield (Gaudry / Diem shape). Large lifts sit near 768 bits |
| isogeny volcanoes | `volcanoes[]` plus one open instance per level (`crater`, `interior`, `floor`). Height at least 2, one of height at least 3. Edges are roots of `Φ_ℓ` |

## Checking a faster implementation

1. Pick an `open` instance whose `solvers` list names the algorithm you
   changed.
2. Ignore the published scalar and recover it.
3. Confirm it equals `relation.scalar`, or that
   `sha256(id || "\n" || scalar)` equals `relation.scalar_sha256`.
4. Time it against the `bench` instances of the same family.  The C
   registry names (`c_registry.txt`, and the curves added in
   `src/curve.c`) are the ones `ca curve --name` and `ca_bench glv`
   already know how to run.

`cargo test -p cryptanalysis-suite ec_challenges` recomputes Koblitz and
subfield orders from the trace recurrence, checks every prime-field
relation with the suite's own group law, and checks every volcano edge
against `Φ_2` or `Φ_3`.
