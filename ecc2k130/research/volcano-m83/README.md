# Volcano descendants of the F_(2^83) Koblitz curve

The ECC2K-130 volcano-descendant study (conductor-263 floor, runs 01-10),
repeated for the repository's `m = 83` test curve

    E0: y^2 + xy = x^3 + 1  over  F_2[z]/(z^83 + z^7 + z^4 + z^2 + 1),
    #E0 = 4 * ELL,  ELL = 2417851639230796216685689 (81 bits, prime)

— the curve the ECC2K-130 client builds as `eccF83.h`
(`ecc2k130/runner/codegen/gen.py`).  The public pair used for transport is the
header's primary `P, Q`; the generator draws `Q = [k]P` and never records `k`.
**No discrete logarithm is computed anywhere in this directory.**

The full write-up is [`report/`](report/) (PDF and Markdown); every number in
it is read from `outputs/`.

## What is different at m = 83

| | ECC2K-130 (m = 131) | this study (m = 83) |
|---|---|---|
| `[O_K : Z[pi]]` | 263 · 146505763881528721 | **6473 · 53676929** |
| nearest conductor prime | 263, split in Q(sqrt(-7)) | **6473, inert** |
| floor size / Frobenius orbits | 262 = 2 × 131 | **6474 = 78 × 83** |
| horizontal conductor-prime maps from E0 | 2 | **0** (all 6474 lines descend) |
| pi on E0[l] | −I, torsion over F_(q^2) | **2514·I, a primitive root: x-coordinates over F_(q^3236) = F_(2^268588)** |
| min noninteger endomorphism degree on the floor | 121,046 | **73,324,526** |
| large-subgroup embedding degree | 118 bits | **74 bits** (still invariant) |
| signed-Frobenius rho | 2^60.81 | **2^37.14** |

The inert conductor prime changes the engineering: the ECC2K-130 route
(Vélu from E0[263] over F_(q^2)) is impossible here, so the floor is built
from a ring class polynomial and the explicit degree-6473 isogenies are
computed in F_(2^268588) by native code.

## Findings (details and every number in `report/`)

* **Floor.** `polclass(−7·6473², 5)` mod 2 splits into 78 degree-83
  factors; all 6474 curves have order 4·ELL; Cl(O_6473) is cyclic of order
  6474 with the prime above 2 of order 83.
* **Explicit descent.** One 268,563-bit ladder on the twist over
  F_(2^268588) gives a point of order 6473 with π = 2514 on it. All 6474
  kernel lines give 6474 distinct Vélu codomains, exactly the class-polynomial
  roots, and none maps back to j = 1. Kernel polynomials of degree 3236 map the
  header's P, Q to three selected descendants. On a floor curve the same
  ladder finds a point of order 6473², the Jordan block.
* **Yield.** The tag eligibility formula holds on all 32,375 exact census
  rows. The only non-injective images are E0's at k = 5, 6, 7, all from
  2P_w + P_(w²) − P_(w⁴) = O, and they add no factor-base rank. Matched
  cardinality leaves ≤ 0.014 % four-summand yield difference.
* **Regularity** follows the membership indicator. At k = 5 every sampled
  descendant has d_reg = 6 + (membership ANF degree). E0 is the one curve below
  its stratum, and swapping its coefficient b = 1 for floor coefficients
  restores it, so this is a crater property.
* **Adapted subspaces.** 25–29 % single-cell gains at k = 8, 9. Two of 6474
  curves clear the 20 % adjacent-dimension gate at k = 8/9 only; every lead
  decays to ≈ 1.0 by k = 13–16.
* **Atlases.** Frobenius atlases over all 78 orbits give 137–513× the
  best chart's solver work. The degree-11 cycle through the reference joins 13
  orbits (1079 charts, paths up to 539 steps), with disjoint columns and 5052×
  the work.
* **End to end.** Public-target probes find zero natural rows, so rank,
  linear algebra and extraction stay null. Signed-Frobenius rho is 2^37.14
  operations.

## Pipeline

| stage | script | output |
|---|---|---|
| ring invariants, Lucas certificates, all orders | `scripts/s00_ring_invariants.py` (stdlib) | `outputs/s00-ring-invariants.json` |
| gamma_2 class polynomial of D = −7·6473² (h = 6474) | `scripts/s01_polclass.gp` (PARI, ~12 min) | `outputs/inventory/H83-mod2-ascending.txt` |
| floor inventory: 78 × 83 curves, order certificates, class group | `scripts/s01_inventory.py` | `outputs/inventory/inventory.json` |
| Run-01 solver census (k = 4 polynomial, all 6475 curves) | `scripts/run01_comparison.py --ids all` | `outputs/run01-comparison/census-*.jsonl` |
| Run-01 solver panel (k = 4 random, k = 5; 161 curves) | `scripts/run01_comparison.py --ids panel` | `outputs/run01-comparison/panel-*.jsonl` |
| exact 3-summand images, k = 4..7, all curves | `scripts/run01_yield_census.py` | `outputs/run01-comparison/yield-census-*.jsonl` |
| Run-02/03 attribution, collisions, rank, counterfactuals, scaling | `scripts/run02_attribution.py` | `outputs/run02-attribution/` |
| toy validation of the native isogeny tool (m = 17, l = 271) | `scripts/s04_toy_validation.py` | `outputs/run04-explicit-descent/toy/` |
| Run-04 explicit degree-6473 descent, 6474 lines, maps, transport | `native/isogeny torsion` + `scripts/s04_descent.py` | `outputs/run04-explicit-descent/` |
| Run-05 embedding degree and 6473-torsion structure | `scripts/s05_embedding.py` | `outputs/run05-embedding.json` |
| Run-06 four-summand yields, probes, solver controls, rho | `scripts/run06_four_summand.py`, `run06_solver_controls.py` | `outputs/run06-four-summand/` |
| Run-07 half-trace pair membership | `scripts/run07_halftrace.py` | `outputs/run07-halftrace/` |
| Run-08 complete-floor adapted subspaces | `scripts/run08_subspaces.py` | `outputs/run08-subspaces/` |
| Run-09 Frobenius-conjugate atlases (all 78 orbits) | `scripts/run09_frobenius_atlas.py` | `outputs/run09-frobenius-atlas/` |
| Run-10 horizontal graph (l = 11..53) and degree-11 atlas | `scripts/run10_horizontal.py`, `run10_atlas.py` | `outputs/run10-horizontal/` |
| figures and report | `scripts/figures.py`, `report/build_report.py` | `outputs/figures/`, `report/` |

Scripts that import Sage run under `sage -python` from `scripts/`;
`s00_ring_invariants.py`, `s05_embedding.py`, `run01_analyze.py`,
`figures.py` and the report builder are plain Python 3.

## Native code (`native/`, AArch64 with PMULL)

`make` builds three things; shared libraries are written to a temporary name
and renamed so running processes keep a valid mapping.

* `isogeny` — arithmetic in F_(2^(83·3236)) as the tower
  F_(2^83)[Y]/(Y^3236 + Y^887 + 1): Kronecker packing into 165-bit slots and a
  PMULL Karatsuba (top level on three threads with `TOWER_THREADS=3`).
  Commands: `torsion` (x-only Montgomery ladder by a 268,563-bit cofactor on
  the quadratic twist), `frobcheck`, `lines` (all l + 1 kernel lines through
  the identity x(P + tau P) = x_P + 1/x_P, which follows from
  tau(P + tau P) = −2P), `kernel` (Berlekamp–Massey on Tr(x^i)).  The Vélu
  codomain of a line needs only v = Tr_(F_Q/F_q) x(generator):
  j = 1/(1 + v + v^2).  `scripts/s04_toy_validation.py` checks every command
  against Sage on m = 17, l = 271, where Sage can build the torsion field.
* `libf83.dylib` — F_(2^83) curve arithmetic for the factor-base studies
  (rational-x tables, lifts and Z/4 tags, exact 3/4-summand images with
  batched inversion, pair-table four-summand probes, Frobenius powers);
  `scripts/check_f83lib.py` cross-checks it against Sage.
* `libcpualarm.dylib` — CPU-time caps for Sage/libSingular stages.  All
  solver caps in this study are process CPU seconds (msolve: RLIMIT_CPU), so
  censoring does not depend on machine load; the ECC2K-130 study used
  wall-clock caps.

## Large inputs not kept in git

`polclass(-7·6473², 5)` has 6475 integer coefficients of up to 202,143 bits
(297 MB as hex).  Only its reduction mod 2 is stored; `s01_inventory.py
--coefficients FILE` re-reduces and hashes a regenerated file
(SHA-256 `ac617bd9…fcb67`, recorded in `inventory.json`).  The torsion points
`outputs/run04-explicit-descent/*.bin` are raw tower elements (52 KB each).
