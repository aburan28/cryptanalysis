# Thirteen-window unit-orbit fixed-base multiplication

The candidate represents a reduced secp256k1 scalar by an Eisenstein pair
`a+bτ`, where `τ=1-ω` and `τ²=3τ-3`, then expands both coordinates in the
integer radix **943**. Each of thirteen positional tables stores one affine
point per orbit under the six Eisenstein units. Online evaluation selects at
most thirteen points and performs at most **twelve mixed additions**, with no
online doubling or `τ` step. This is an optional memory point on the same
fixed-base, public-scalar frontier as U14: the declared cap is **140 MiB** of
retained table payload, rather than U14's 90 MiB cap.

## Exact coverage argument

Use the existing equilateral scalar kernel lattice with determinant and
side-norm `n`, the secp256k1 group order. Its nearest representative `z` has
Eisenstein norm at most `n/3`. For an integer radix `R`, choose each digit
as the nearest element in its residue class modulo `R`. The hexagonal
covering radius gives `||digit|| <= R/sqrt(3)` for the norm's Euclidean
length. If `z_(i+1)=(z_i-digit_i)/R`, then

`||z_13|| <= sqrt(n/3)/R^13 + (1/sqrt(3))*sum_(j=0)^12 R^(-j)`.

At `R=943`, this is strictly less than one. The integer certificate checks
the sufficient inequality

`(ceil(sqrt(n)) + sum_(j=1)^13 R^j)^2 < 3 R^26`.

The only Eisenstein integer of norm below one is zero, so thirteen digits
always reconstruct the chosen representative. The existing four-corner
nearest-representative routine and four-corner digit routine attain the
stated hexagonal bounds. Since `gcd(943,6)=1`, every nonzero residue modulo
943 has six distinct unit images. Each table has exactly
`1+(943²-1)/6 = 148,209` entries including the identity, giving
**1,926,717 point entries** and **138,723,624 point bytes** (132.297 MiB).
Code maps and orbit digits are charged separately in retained payload.

## Frozen screen and implementation gates

1. Commit this protocol and `radix943_screen.py` before running its
   deterministic 4,096-scalar panel. The law is Python `Random(20261009)`,
   one 256-bit draw reduced modulo `n` per case. Also check `0`, `1`, `2`,
   `n-2`, and `n-1`. Record an input digest, reconstruction counts, digit
   counts, maximum initial norm, and the exact inequality in JSON. Preserve
   failures as failures.
2. Enumerate every radix-943 residue pair to check the digit congruence and
   norm bound. Construct and check the unit-orbit atlas and all table slots.
   The point table must stay below 140 MiB retained payload. A point-budget
   estimate alone is not a memory measurement.
3. Replay every point in the existing 129-case independent fixture, including
   the scalar with an omitted sparse-comb top row. Check fresh full-range
   scalars and boundary cases against independent scalar multiplication.
   The optional format must preserve the original U14/U15/U16 results.
4. Freeze a same-binary paired U14 versus radix-943 manifest. Its internal
   `online_ms` includes scalar reduction, recoding, table lookup, point
   accumulation, affine conversion, and correctness assertion; table build
   remains separate reusable setup. Report table construction and memory.
   Accept a CPU wall-time ratio only on a host that passes the strict
   isolation and noise gates in `docs/ISOLATED_BENCHMARKS.md`.

The point-operation boundary is the number of mixed additions after the
first selected point. Any comparison must include the higher table memory,
recoding cost, unit actions, and full online interval. Academic priority
requires a separate prior-art review; the six-unit action and `τ`-adic
ideas appear in the supplied paper.
