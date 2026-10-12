# Why the minimum-cover dynamic program may use partitions

The frozen [proof](PROOF.md) uses the fact that a cover of a tau cycle
can be converted to a partition into consecutive admissible segments.
Here is the eligibility step in that conversion.

Suppose a seed at class `v` covers through `tau^k(v)`, with `k<=2`, and
its first class not already assigned to a preceding seed is `tau^j(v)`.
The minimum-norm digit at that class has norm at most `3^j N(d_v)`.
Covering the remaining `k-j+1` classes then requires norm at most
`3^(k-j) * 3^j N(d_v) = 3^k N(d_v) <= 1024^2`. Moving the seed to its
first exclusive class therefore preserves admissibility. Applying this
operation around the cycle removes overlaps without increasing the
number of seeds. The dynamic program checks every possible start of the
segment covering its fixed origin and every admissible length.

This elaborates the proof frozen before the scalar panel; it changes no
atlas, code, input law, or selected seed count.
