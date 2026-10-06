# Elliptic-curve challenges

A generated corpus of elliptic curves for the suite's Pollard rho, index
calculus, and endomorphism benchmarks. The curves are research instances.
The catalog checked in here has 263 curves, with field sizes from 2 bits
through 771 bits, including prime-field and binary curves at 768 bits.
They are not parameter sets for deployment.

Regenerate everything with:

```sh
python3 challenges/ecc/generate.py
```

The script is deterministic (a fixed LCG and SHA-256 hash-to-curve) and
uses only the Python standard library. `catalog.json` is the index.
`curves/<id>.json` is the full record. `inspect/<id>.json` is the subset
`ca-ic inspect` accepts, written only when the subgroup order passes a
probable-prime screen and the model is one the inspector understands
(prime-field short Weierstrass with modulus at least 5, or binary
Weierstrass).

## What varies

Field shapes:

- prime fields, from around 2^12 through 2^768;
- `F_2^m` for prime and composite `m`, including 61, 127, 571, and 768;
- scaled-down ECC2K-130: `f2-koblitz-a0-m{41,83,97,103,107}` are every
  prime `m` in 24..130 where `y^2 + xy = x^3 + 1` has order 4·prime, as
  ECC2K-130 (`f2-koblitz-a0-m131`) does. `ecc2k130/small/` solves them on
  Metal;
- characteristic 3, ordinary and supersingular, at prime degrees and at
  composite degrees (`3^4`, `3^5`, `3^6`, and products such as `2·3^5`);
- odd-characteristic extensions `F_p^k` with both prime and composite `k`,
  including curves defined over a subfield and base-changed.

Curve geometry:

- `j = 0` and `j = 1728`, with quadratic and sextic twists;
- class-number-1 discriminants −7, −8, −11, −19, −43, −67, −163, and a
  few class-number-2 discriminants;
- random `j`, smooth group orders, and anomalous curves (trace 1);
- supersingular curves, where the MOV embedding degree is small;
- a Barreto–Naehrig pairing-friendly sample when both `p(z)` and `n(z)`
  are probable primes;
- Koblitz curves `y^2 + xy = x^3 + a x^2 + 1` for `a ∈ {0, 1}`;
- binary curves that are not Koblitz, and supersingular binary curves
  `y^2 + y = x^3 + x + b`;
- isogeny volcanoes. Conductor height is recorded for every CM prime-field
  curve that has one. `fp-volcano-d7-l3-exhibit` is a rational 3-volcano of
  height 3: the record lists a model at the crater, on each slope level, and
  on the floor.

## Certificates and tiers

Group orders are computed before the scalar multiplication that checks
them: a CM representation `4p = t^2 − D v^2`, the Koblitz Frobenius
recurrence, a trace lift `t_k = t t_{k−1} − q t_{k−2}`, enumeration, or
Hasse-window point counting. `order_certificate` names which one.

`verification` is `scalar-annihilation` when `[n]G = O` was checked with
the group law, and `trace-recurrence` when the extension was too large
for that check. Prime-field curves are always scalar-checked. Binary
curves are scalar-checked. Characteristic-3 and `F_p^k` curves are
scalar-checked when the degree is small or the field has at most about
220 bits.

`tier` is `check` when that scalar check ran and the published subgroup
has at most 48 bits. Those records store `known_log`, and
`target = [known_log] generator`. Everything else is `open`: the target
is a hash-to-curve point (times the cofactor, when that multiple was
computed), and the discrete log is not stored.

## Using a challenge

From `suite/`:

```sh
cargo build --release -p cryptanalysis-suite --bin ca-curves --bin ca-ic --bin ca-suite
./target/release/ca-curves list --tag volcano
./target/release/ca-curves show f2-koblitz-a0-m61
./target/release/ca-ic inspect --file ../challenges/ecc/inspect/f2-koblitz-a1-m8.json
./target/release/ca-curves rho-job fp-j0-b32 --seed 1 > /tmp/fp-j0-b32.json
./target/release/ca-suite rho-collab work --job /tmp/fp-j0-b32.json --node local --threads 2
```

`rho-job` is only for prime-field short-Weierstrass records. The job
carries the curve, the generator, and the target. It does not carry
`known_log`. Grade a `check` instance by comparing a recovered scalar
with the value in the curve record.

Binary and extension records are the index-calculus inputs. `suggested_solvers`
is a list of applicable algorithm names (Pollard rho, GLV, Semaev,
Gaudry–Diem, Weil descent, Smart, MOV, Pohlig–Hellman, isogeny volcanoes).
It is not a procedure.

`ca-ic inspect` checks the field polynomial, the curve equation, and
`[r]P = O` when the coordinates are integers in a single polynomial basis.
Tower records (`binary-tower`, odd-characteristic extensions) keep
coefficient vectors and are not inspector files. Inspecting a 768-bit
binary curve runs those scalar multiplications and is slow.

The C library in the repository root still speaks 64-bit Montgomery
arithmetic. Prime-field challenges at most 64 bits can be passed to `ca`
as `--group ec` parameters; larger ones belong to the Rust suite.
