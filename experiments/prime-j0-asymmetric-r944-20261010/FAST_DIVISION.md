# Exact signed-magnitude division by radix 944

The thirteen-window recoder divides each Eisenstein coordinate by
`944=16*59`. The certified initial representative and the bounded digit
recurrence keep each coordinate magnitude below `2^129`. For a magnitude
`0<=x<2^129`, write `x=16y+l`, `0<=l<16`, and `y=H*2^64+L`. Let
`K=floor((2^64-1)/59)`, so `2^64=59K+5`. Divide the two 64-bit words by
the compile-time constant 59:

`H=59q_H+r_H`, `L=59q_L+r_L`, with `0<=r_H,r_L<59`.

Set `c=floor((5r_H+r_L)/59)` and `t=(5r_H+r_L) mod 59`. Then

`q=q_H*2^64+r_H*K+q_L+c`, `r=l+16t`.

Expanding `2^64=59K+5` gives `x=944q+r` with `0<=r<944`.
The low quotient word fits in 64 bits: when `q_L=K`, the attainable
`r_L<=4` gives `r_H*K+q_L+c<=59K+4=2^64-1`; when `q_L<K`, the
possible extra unit of `c` is offset by the smaller `q_L`. For negative
coordinates, apply the sign to both `q` and `r`. If atlas digit `d` is
congruent to `x` modulo 944, the exact next coordinate is
`q+(r-d)/944`, a small signed correction.

`fast_division.py` checked both signs of 23 boundary inputs, 100,000
deterministic 129-bit values, exact reconstruction, remainder range, and
five congruent atlas-digit shifts. The native implementation still needs
its own boundary and same-input point checks before using this quotient
in a measured evaluator.
