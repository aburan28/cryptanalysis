# Exact signed-magnitude division by radix 640

The first six windows divide their Eisenstein coordinates by 512 with a
shift. The final eight use `640=128*5`. The certified initial pair has
`N(a,b)<=n/3`; completing squares gives `|a|<=2*sqrt(N)` and
`|b|<=2*sqrt(N/3)`, both below `2^129`. The digit recurrence with
radices at least 512 and bounds no larger than the radix preserves this
coordinate limit. For a coordinate magnitude `0<=x<2^129`, split
`x=128*y+l` with `0<=l<128`, then write
`y=H*2^64+L`. Let `K=(2^64-1)/5`, so `2^64=5K+1`.
Dividing the two 64-bit words separately gives

`H=5q_H+r_H`, `L=5q_L+r_L`, with `0<=r_H,r_L<5`.

The exact quotient and remainder are

`q=q_H*2^64+r_H*K+q_L+floor((r_H+r_L)/5)`,

`r=l+128*((r_H+r_L) mod 5)`.

Expansion using `2^64=5K+1` proves `x=640q+r` and `0<=r<640`.
The low quotient word never overflows: `r_H*K+q_L+carry <= 2^64-1`
for the attainable word remainders. For negative `x`, apply its sign
to `q` and `r`; this is the signed-magnitude quotient convention in the
native evaluator. If the atlas digit `d` has `d ≡ x (mod 640)`, the next
coordinate is exactly `q+(r-d)/640`, where `(r-d)/640` is a small
signed integer.

The [validation script](fast_division.py) checks both signs of the listed
boundary values, 100,000 deterministic random 129-bit values, the
remainder range, exact reconstruction, and five congruent digit shifts.
The formulas require two constant divisions by five per coordinate,
which a native compiler can lower to fixed multiplications and shifts.
The native implementation and full online cost remain to be measured.
