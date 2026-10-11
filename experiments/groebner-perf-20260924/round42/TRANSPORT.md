# Exact lookup representation of witness transport

Fix the explicit monic modulus, its degree n, and a binary annihilator row a.
Let M_u denote multiplication by the represented polynomial u in that quotient.
For the witness map T_a(u) = a M_u, distributivity gives

T_a(u XOR v) = T_a(u) XOR T_a(v).

Therefore the n bit images T_a(z^j), 0 <= j < n, determine the entire map.
For nibble h and value v in 0..15, store the XOR of the bit images selected by
v at positions 4h..4h+3. Images beyond degree n-1 are zero; runtime inputs
outside the n-bit domain are rejected by the diagnostic API. XORing the
ceil(n/4) selected table entries is exactly T_a(u).

The native setup computes each bit image from repeated quotient multiplication
by z and explicit parity against a. The independent validation instead uses
ordinary polynomial multiplication to construct M_u. It covers every nibble
entry, all 128 values for the toy degree-seven quotient, random and boundary
values on every supported n/ell shape, both optimized and UBSan builds,
output extents, disablement and replacement of the modulus.

This representation lemma needs only quotient-ring distributivity. Its use as
a normalization witness still requires the original stronger runtime checks:
all quadratic columns match alpha*Gamma, alpha is a unit, and the computed
inverse satisfies alpha*inverse=1. The existing zero-scalar path, mismatch,
nonunit and work-budget fallbacks remain necessary.

For r witness rows and n=31, transport uses 8r table lookups/XORs rather than
31r parity evaluations. Table storage is r*8*16*4 bytes, plus vector metadata;
setup and allocation are outside target-dependent query time and retained
separately. Persistent table capacity is included in workspace accounting.
Peak allocation during configuration is not claimed by that workspace value.
Every runtime lookup counts against the same administrative work budget.

These are operation and storage counts for a fixed word-size implementation,
not a query-time speedup or a new general asymptotic algorithm. This is the
standard use of lookup tables for a binary-linear map within the guarded
normalization constructor.
