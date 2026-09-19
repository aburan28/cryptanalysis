# Algorithms

This document describes what the library implements, the mathematics behind
each algorithm, the design decisions taken in the implementation, and the
measured constants.  All cost figures use the unit

```
S = group operations / sqrt(N)
```

where `N` is the group order (whole-group problems) or the interval width
(interval problems).  In that unit Pollard rho is a flat `S ~ 1.25` at every
size, so "is this better than rho" is one column.  See
[BENCHMARKS.md](BENCHMARKS.md) for the tables.

## Setting and scope

Everything is written against a generic cyclic group interface
(`ca_group`, [ca_group.h](../include/cryptanalysis/ca_group.h)) with two
concrete instances:

* a subgroup of `(Z/pZ)^*`, and
* a subgroup of `E(F_p)` for a short Weierstrass curve `y^2 = x^3 + ax + b`.

Field arithmetic is 64-bit Montgomery arithmetic (`p < 2^64`), so every
problem the library solves lives in a group of order below `2^64`.  That is
deliberate: the purpose is to *measure* the constants of the algorithms and
to give language runtimes a fast native core, not to attack cryptographic
sizes.  Every constant in this document was measured, not quoted.

Group elements are 32-byte POD values.  Curve points are affine; the
parallel walks use Montgomery's simultaneous-inversion trick
(`ca_group_batch_op`) so that one field inversion serves 256 additions.
Measured on one core: 232 ns per affine addition with a private inversion,
21.8 ns per addition in batches of 256, 5.9 ns per Montgomery
multiplication in `Z_p^*`.

## Baby-step giant-step (`ca_bsgs.h`)

Shanks' algorithm for `x` in `[lo, hi]` with `x*G = H`.  With `m` baby
steps `jG` (`0 <= j < m`) stored in a hash table keyed by a 64-bit element
fingerprint, the giant steps walk `H - (lo + im)G` and look up the table.
Every match is verified by a scalar multiplication, so fingerprint
collisions cannot yield a wrong answer.

* Default `m = ceil(sqrt(width))`; average cost `1.5 sqrt(width)`
  (measured `S = 1.44 .. 1.66`), worst case `2 sqrt(width)`.
* Memory 24 bytes per baby step.
* `ca_bsgs_table_*` keeps the baby-step table for many logarithms to the
  same base (each subsequent solve costs only the giant steps).

## Pollard rho (`ca_rho.h`)

Teske's `r`-adding walk with multipliers `M_i = a_i G + b_i H`, state
`(Y, a, b)` with `Y = aG + bH`, step `Y <- Y + M_{idx(Y)}`.  Distinguished
points (hash with `dp_bits` trailing zero bits) are stored with their
`(a, b)` in a shared table (van Oorschot-Wiener); a second arrival with a
different `(a, b)` gives `(b - b') x = a' - a (mod n)`.  For composite `n`
the congruence is solved by gcd and every candidate verified.

Implementation points:

* Threads run batches of `W` walks; each batch step is one
  `ca_group_batch_op` (one inversion for `W` curve additions).
* `r`, `W` and `dp_bits` are chosen automatically from `n` and the thread
  count so that neither the multiplier table nor the walk start-ups (each
  costs about `3 log2 n` operations) exceed a small fraction of
  `sqrt(n)`, and so that the expected number of distinguished points is
  about 32 per walk (bounded above at `2^24` table entries).
* Walks that run `24 * 2^dp_bits` steps without a distinguished point are
  restarted (they are in a cycle without one).

**Negation map** (elliptic curves).  Every point is replaced by the
canonical member of `{Y, -Y}` (the one with the smaller Montgomery `y`),
negating `(a, b)` when needed, which shrinks the search space by 2 and the
expected cost by `sqrt(2)`.  The walk on classes is only well defined if
`idx()` is evaluated on the canonical form, which it is.  Fruitless cycles
are handled as in Bernstein-Lange-Schwabe, *On the correct use of the
negation map in the Pollard rho method*:

* 2-cycles: the look-ahead rule "if `idx(Y + M_i) = i` use `M_{i+1}`
  instead" (iterated), which keeps the walk a deterministic function of
  `Y` and reduces the 2-cycle rate from `1/(2r)` to about `1/(2r)^2`;
* longer cycles: a sliding window compares each new point with a point
  saved every 64 steps; on a hit the cycle is traversed once, its minimum
  (by hash) found, and the walk escapes deterministically to `2 * min`.
  Because the escape depends only on the cycle, two walks that merged
  inside a cycle stay merged.

With the negation map, `r` is allowed to grow to 1024 (fewer fruitless
cycles); without it the default is 32.

Measured (whole group, prime order, one thread): `S = 1.26` (`Z_p^*`,
32 bits), `S = 0.79 .. 1.7` (curves with negation map, 24 - 40 bits; the
spread at 5 repetitions is statistical, the standard deviation of a single
rho run is about half its mean).

## Pollard kangaroo / lambda (`ca_kangaroo.h`)

Interval logarithm `x` in `[lo, hi]` without the `O(sqrt(width))` memory of
BSGS.  Tame kangaroos start at known exponents around the middle of the
interval, wild kangaroos at `H + small offset`; both jump by `2^j G` where
`j` is a hash of the current point.  Jump sizes are chosen so that the mean
jump is about `(number of kangaroos) * sqrt(width) / 4` (van Oorschot-
Wiener).  A tame and a wild kangaroo landing on the same distinguished
point give `x = tame position - wild distance`.  Same-herd collisions
re-seed one of the two kangaroos.

Measured: `S = 1.4 .. 2.3`, in line with the textbook `2 sqrt(width)` and
better than it for wide intervals in `Z_p^*`.  Memory is a few thousand
distinguished points regardless of the width.

## Two grumpy giants and a baby (`ca_grumpy.h`)

Bernstein and Lange (ANTS X, 2012; ePrint 2012/294).  After shifting so
that `x' = x - lo` lies in `[0, N)`, three walks are interleaved and every
point goes into one table:

```
baby    B_j = j G
giant 1 U_i = H' + i m G            (forwards from H')
giant 2 V_i = 2H' - i (m+1) G       (backwards from 2H')
```

Collisions: `B_j = U_i` gives `x' = j - im`; `B_j = V_i` gives
`2x' = j + i(m+1)`; `U_i = V_k` gives `x' = im + k(m+1)`.  All congruences
are taken modulo the group order when it is known (so the `2x'` case is
resolved by halving modulo an odd `n`, or by trying both halves for an even
`n`), and every candidate is verified.

The step `m` is `alpha * sqrt(N)`.  Rather than quote a value, we
simulated the three walks exactly in exponent space and then confirmed
with the real implementation (400 instances each):

| setting                       | alpha 0.5 | 0.6  | **0.7**  | 0.8  | 1.0  |
|-------------------------------|-----------|------|----------|------|------|
| whole group of order n        | 1.20      | 1.18 | **1.18** | 1.26 | 1.33 |
| interval of width 2^22 (no wrap) | 1.97   | 1.81 | **1.78** | 1.78 | 1.98 |

(interleaved BSGS in the same simulation: 1.33 in the whole group, the
known `4/3` figure.)  The default is therefore `alpha = 0.7`.  The paper's
headline numbers are for the whole-group setting, where giant steps wrap
modulo `n` and every collision type is productive; in a narrow interval
one collision type is mostly lost and the constant is 1.78, still better
than kangaroo (about 2) at the price of `O(sqrt(N))` memory.  The paper's
success probability after `1.5 sqrt(n)` operations is `0.71875`; our
simulation gives `0.70` at `n = 4093`.

## Pohlig-Hellman (`ca_pohlig.h`)

Splits a logarithm in a group of order `n = prod q^e` into `e` logarithms
in groups of prime order `q` per factor (digit by digit) and recombines
with the CRT.  `ca_dlog_prime_order` dispatches each prime-order problem to
brute force (tiny), BSGS (`q <= 2^36` by default), rho (whole group) or
kangaroo (interval); the solver can be forced.  `ca_dlog` is the
one-call driver.

## Cheon's attack on the strong Diffie-Hellman problem (`ca_cheon.h`)

Cheon (EUROCRYPT 2006, J. Cryptology 2010).  Let `G = <g>` have prime order
`p` and let `d | p-1`.  Given `g`, `g^alpha` and `g^(alpha^d)`, the secret
`alpha` can be recovered in about `2 sqrt((p-1)/d) + 2 sqrt(d)`
exponentiations instead of `sqrt(p)` group operations.  Writing
`alpha = zeta^k` for a primitive root `zeta` of `(Z/pZ)^*`:

1. `eta = zeta^d` has order `(p-1)/d` and `g^(alpha^d) = g^(eta^k)`, so
   `k mod (p-1)/d` is a BSGS over the orbit `u -> g^(eta^u)` (baby steps
   `g^(eta^j)`, giant steps `(g^(alpha^d))^(eta^(-m i))`);
2. with `k = k1 + ((p-1)/d) k2`, `theta = zeta^((p-1)/d)` has order `d`
   and `g^alpha = (g^(zeta^k1))^(theta^k2)`: the same BSGS for `k2`.

Each step is an exponentiation (`~1.5 log2 p` group operations), which is
why the attack only wins when `p-1` has a divisor near `sqrt(p)`.
`ca_cheon_best_divisor` picks the divisor minimising the cost.
Measured against rho on the same instance: 1.9x fewer group operations at
32 bits, 4.2x at 40 bits, 18.6x at 48 bits (see BENCHMARKS.md).  The
`d | p+1` variant (which needs `F_{p^2}` exponent arithmetic) is not
implemented.

## Index calculus in `(Z/pZ)^*` (`ca_indexcalc.h`)

### Relation collection

**Linear sieve** (Coppersmith, Odlyzko, Schroeppel 1986), the default.
With `H = ceil(sqrt(p))` and `J = H^2 - p`,

```
(H + c1)(H + c2)  =  J + (c1 + c2) H + c1 c2   (mod p),
```

and the right-hand side is only about `C sqrt(p)` in size for
`|c1|, |c2| <= C`, so it is `B`-smooth far more often than a random residue.
For each `c1` the values are linear in `c2`, so smoothness is detected by a
classical sieve over `c2` (root `c2 = -(J + c1 H)/(H + c1) mod q` for each
prime `q <= B`) followed by trial division of the survivors.  Unknowns are
the logs of the primes up to `B` and of the `2C + 1` numbers `H + c`; the
constant `log(-1) = (p-1)/2` and the relation `zeta = prod q^e` (which
pins `log zeta = 1`) go to the right-hand side.  Threads split the `c1`
range.  Heuristic complexity `L_p[1/2, 1]`.

**Random exponents** (the textbook method): `zeta^e mod p` tested for
`B`-smoothness by trial division; `L_p[1/2, 2]`.  Kept for comparison and
as an independent check of the linear algebra.

The `(B, C)` defaults come from a small table indexed by the bit length of
`p` (`ca_ic_auto_params`), tuned with `ca_bench ic`.

### Linear algebra

Logarithms are needed modulo `p - 1 = prod q^e`.

* For primes `q <= 2^24` the factor-base logs are computed *directly* with
  Pohlig-Hellman in the small subgroups (cheap: `e * sqrt(q)` steps per
  prime).  This avoids linear algebra over tiny fields entirely.
* For each larger `q` the relation matrix is solved modulo `q`: structured
  Gaussian elimination first (singleton columns are removed together with
  their rows and recovered by back-substitution), then the Lanczos
  iteration on `A^T D A` with a random diagonal `D` (LaMacchia-Odlyzko),
  with a dense fallback for small systems.  Row and column products are
  accumulated in 128-bit integers and reduced once, so a matrix-vector
  product costs one `%` per row.  2000 unknowns solve in about 1 s at any
  64-bit `q`.  For `e > 1` the solution is Hensel-lifted.
* The CRT combines the pieces, and every factor-base logarithm is verified
  (`zeta^log = q mod p`) before it is used.  An unverified log is simply
  unavailable to the individual-log stage; a wrong answer is never
  returned.

### Individual logarithms

`h zeta^e` is tested for `B`-smoothness for random `e` until it factors
over the verified factor base; then `log h = sum a_i log q_i - e`.  At
these sizes a few hundred trial divisions suffice (measured 150 - 430
tries), so no descent stage is needed.  A non-primitive base `g` is
handled by dividing logarithms modulo `ord(g)`.

Measured with 4 threads (safe primes): 32 bits 0.03 s, 40 bits 0.09 s,
48 bits 0.3 s, 56 bits 1.3 s, dominated by Lanczos.  Rho needs about
`1.3 sqrt(q)` operations on the same groups, i.e. `1.7e8` operations
(about 1.5 s here) at 56 bits: the crossover with rho on this hardware is
around 56 bits, and the gap widens quickly above it.

### Relationship to the state of the art

* For prime fields the state of the art is the number field sieve
  (`L_p[1/3]`, e.g. CADO-NFS); the linear sieve is the strongest of the
  `L[1/2]` methods and the right tool below ~100 bits.  NFS is out of
  scope for a 64-bit toolkit.
* For elliptic curves over prime fields **no index calculus is known**;
  the best attacks are the generic square-root algorithms above.  Index
  calculus on curves (Semaev summation polynomials, Gaudry, Diem, Petit-
  Quisquater) applies to extension fields `F_{q^n}` and, as of today, does
  not beat rho at any cryptographic size.  A sibling research repository
  tracks that literature and its experiments; this library provides the
  reference rho/BSGS/kangaroo implementations those comparisons are made
  against.

## Auxiliary algorithms

* Deterministic Miller-Rabin for 64-bit integers (12 bases).
* Pollard-Brent factoring with Montgomery arithmetic and batched gcds.
* Tonelli-Shanks square roots, primitive roots, multiplicative orders.
* Mestre's baby-step giant-step point counting for `E(F_p)`
  (`O(p^{1/4})`, with the quadratic-twist fallback when the group exponent
  is small), used by the tests and the `ca ec-order` command.

## References

* D. Shanks, *Class number, a theory of factorization and genera*, 1971.
* J. Pollard, *Monte Carlo methods for index computation (mod p)*, 1978.
* P. van Oorschot, M. Wiener, *Parallel collision search with cryptanalytic
  applications*, J. Cryptology 1999.
* E. Teske, *On random walks for Pollard's rho method*, Math. Comp. 2001.
* D. J. Bernstein, T. Lange, P. Schwabe, *On the correct use of the
  negation map in the Pollard rho method*, PKC 2011.
* D. J. Bernstein, T. Lange, *Two grumpy giants and a baby*, ANTS X 2012.
* S. Galbraith, P. Wang, F. Zhang, *Computing elliptic curve discrete
  logarithms with improved baby-step giant-step algorithm*, AMC 2017.
* J. H. Cheon, *Security analysis of the strong Diffie-Hellman problem*,
  EUROCRYPT 2006; *Discrete logarithm problems with auxiliary inputs*,
  J. Cryptology 2010.
* D. Coppersmith, A. Odlyzko, R. Schroeppel, *Discrete logarithms in
  GF(p)*, Algorithmica 1986.
* B. LaMacchia, A. Odlyzko, *Solving large sparse linear systems over
  finite fields*, CRYPTO 1990.
* J.-F. Mestre, *Formules explicites et minoration de conducteurs de
  variétés algébriques*, 1986 (point counting).
