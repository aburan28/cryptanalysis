# ECC2K-130 isogeny class: ground truth for the 263 curves

This directory holds the reference data for E0 (the Certicom ECC2K-130 Koblitz curve)
and the 262 curves one level below it in its 263-volcano (the conductor-263 "floor"
curves). Everything here was computed by `build_ground_truth.py`, which ran in about
60 s with Sage 10.9 / PARI. Every run re-checks the facts listed below and stops with
an assertion error if any of them fails.

## Files

| file | content |
|---|---|
| `ground_truth.json` | `meta` plus one record per curve for all 263 curves |
| `ecc2k.py` | the loader: `load() -> (K, curves)`, plus the constants `N, t, f, p, q, CARD, TAU_EIGEN` |
| `test_ecc2k.py` | the loader test (`sage -python test_ecc2k.py`) |
| `build_ground_truth.py` | the script that builds everything here |
| `SHA256SUMS` | SHA-256 checksums of the outputs |
| `build_log.json` | a log of each step, with timings and the result of each check |
| `primality_certificates.json` | PARI `primecert` ECPP certificates for N and p |
| `class_polynomial_D-484183.hex` | the integer coefficients of H_D, D = -7*263^2, in hex, one per line from low degree to high |

## Field and encoding

- F_q, q = 2^131. The field is written in the polynomial basis F_2[z]/(z^131 + z^13 + z^2 + z + 1).
  - `modulus_int` = 2722258935367507707706996859454145699847.
  - This modulus is the one the repo uses (`ecc2k130/codegen/field.py` says "Certicom states them in polynomial basis"). To check it, the build puts the repo's Certicom generator (`ecc2k130/metal/selection-20260921.json`, `generatorPolynomial`) on E0 and confirms it has order N.
- Field elements are stored as integers in decimal strings. Bit i of the integer is the coefficient of z^i, which is what Sage's `K.from_integer` and `u.to_integer()` use.
- Curves have the form **y^2 + x y = x^3 + a2 x^2 + b**. In Sage this is `EllipticCurve(K, [1, a2, 0, 0, b])`, and j = 1/b.

## `ground_truth.json`

`meta` holds:
- the field: `modulus_int`, `modulus`, `encoding`, `curve_form`, `q`
- the group order: `t`, `N`, `card` (= 4N) and `twist_card`
- the discriminants and class number: `f`, `p`, `D_frobenius` (= t^2 - 4q = -7 f^2), `D_ring_class` (= -484183), `h_D` (= 262)
- `class_polynomial_coeff_hex_sha256`
- `E0_tau_eigenvalue`
- `labels_source`, `method` and `sage_version`

Each entry in `curves` looks like this (all integers are decimal strings):

```
{label, orbit ("crater"|"A"|"B"), frob_index (0..130), level (1 for E0, 263 for floor),
 j_int, b_int, a2, order_verified: true, order_pari, twist_order_pari, order_point_proof: true}
```

The curves appear in the order E0, A000..A130, B000..B130.

## Labels

These are the Codex labels, reproduced exactly:
- The two degree-131 F_2-irreducible factors of H_D mod 2 are A and B. A is orbit 0 in Sage's `factor()` order.
- X000 is the root of its factor with the smallest integer value, and X_k has j(X_k) = j(X000)^(2^k).
- So the Frobenius map (x, y) -> (x^2, y^2) sends X_k to X_{k+1 mod 131}. `ecc2k.frobenius_next` gives that label.

We matched our labels to Codex's in four ways:
- Our j and b for A000 and B000 equal those in Codex's `public-cm-inventory/inventory.json`.
- Our A factor has the same exponent list as Codex's orbit-0 `j_minpoly`.
- The SHA-256 of the H_D coefficient list equals Codex's `be41b564…ea475`.
- Codex's run-03 fingerprints match for E0, A010, A112, A127, B000 and B095 at k = 6 and 7. These are `factor_base_x_count`, which counts the liftable x in span{1..z^(k-1)}, and the fact that `target_x` lies in the N-subgroup.

The rules come from Codex's `build_inventory.py` and `run-01/executed-source.py` (`curve_inventory`).

## What is verified (see `build_log.json`)

- **Field and E0:**
  - z^131+z^13+z^2+z+1 is irreducible.
  - The trace t = -22283658519494248867 comes from the Lucas recurrence for tau (t_1 = -1), and PARI `ellcard` on E0 gives the same #E0 = 4N.
  - #E0(F_2) = 4.
- **Primality:**
  - N (129.0 bits), p = 146505763881528721 (57.02 bits) and 263 are prime. We checked this with Sage `is_prime(proof=True)` and PARI `isprime`.
  - PARI `primecert` built an ECPP certificate for N, and `primecertisvalid` accepted it. For p < 2^64, PARI's certificate is just p itself, because BPSW is deterministic below 2^64.
- **Discriminant and conductor:**
  - t^2 - 4q = -7 f^2, with f = 263·p.
  - kronecker(-7, 263) = +1.
  - h(-7) = 1 and h(-7·263^2) = 262, both from PARI `qfbclassno`.
  - ord_131(2) = 130.
- **The class polynomial H_D:**
  - PARI `polclass(-484183)` equals Sage `hilbert_class_polynomial(-484183)`.
  - It has degree 262, and its largest coefficient has 17322 bits.
  - Mod 2 it is squarefree and splits into exactly two irreducible factors of degree 131.
- **263-isogenies:**
  - PARI `polmodular(263, 0, Mod(1,2))` gives Phi_263(1, Y) mod 2, and it equals (Y+1)^2 · H_D(Y) mod 2.
  - So the 264 263-isogenies from j = 1 are 2 horizontal ones (back to j = 1) and 262 that go down to exactly the 262 floor j values.
- **Roots:** each factor has 131 distinct roots in F_q, and they are exactly the 131 Frobenius conjugates of the base root. All 262 j values are distinct and none is 0 or 1.
- **Group order, for every one of the 263 curves:**
  - Both twists, a2 = 0 and a2 = 1, were point-counted with PARI (`cardinality(algorithm='pari')`). Exactly one has order 4N, and **it is a2 = 0 for all 263 curves**. The other has order q+1+t.
  - A second, independent proof of the order: take a random point P with [4]P ≠ O and check [N][4]P = O. This works because N > 4√q, so 4N is the only multiple of N in the Hasse interval.
- **tau on E0:**
  - tau(x, y) = (x^2, y^2) acts as [s] on the order-N subgroup, with s = 196511074115861092422032515080945363956.
  - s is a root of s^2+s+2 mod N, and it matches the repo's `frobeniusEigenvalue`.

## What is not covered

- The levels with conductor p and 263·p have about 2^57 classes each. They are not listed here.
- End(floor curve) = Z + 263·O_K follows from H_D (by CM theory) and from the Phi_263 factorization. We did not compute it separately for each curve.

## Loader

```python
import sys; sys.path.insert(0, "/Volumes/SSD990/ecdlp-hardness-work/ground_truth")
import ecc2k                      # constants work under plain python3 too
K, curves = ecc2k.load()          # needs Sage (sage -python); dict of 263 curves, ~3 s
K, sub = ecc2k.load(["E0", "A090"], check=True)   # check=True re-verifies j and the order (about 65 s for all 263 curves)
E = ecc2k.curve("B021"); x = ecc2k.dec(12345); ecc2k.enc(x)
ecc2k.N, ecc2k.t, ecc2k.f, ecc2k.p, ecc2k.q, ecc2k.CARD, ecc2k.TAU_EIGEN, ecc2k.RECORDS["A000"]
```

To rebuild, run this. Nothing is written outside this directory.

```
export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
sage -python build_ground_truth.py
```

The build reads Codex's `inventory.json` and its run-03 `*.jsonl`, which are small, read-only files.
