# Exact two-limb division by 384

Write the nonnegative magnitude of a signed Eisenstein coordinate as
`x = 128*y + t`, with `0 <= t < 128`. Then

`floor(x/384) = floor(y/3)` and `x mod 384 = 128*(y mod 3) + t`.

The certified representative has Eisenstein norm at most `n/3`, where
`n` is the secp256k1 order. Completing the square gives
`N(a,b) >= a²/4` and `N(a,b) >= 3b²/4`. Consequently
`|a| <= 2*sqrt(n/3) < 2^129` and
`|b| <= (2/3)*sqrt(n) < 2^128`. A nearest radix-384 digit coordinate
has magnitude less than `2*384/sqrt(3) < 444`. Each later coordinate
has magnitude at most `(previous_magnitude + 444)/384`, preserving the
`2^129` bound. Thus `y = x >> 7` fits in 122 bits and has two 64-bit
limbs.

Let `y = h*2^64 + l`, `h = 3H+r_h`, `l = 3L+r_l`, and
`K=(2^64-1)/3`. Because `2^64=3K+1`,

`floor(y/3) = H*2^64 + r_h*K + L + floor((r_h+r_l)/3)`,

`y mod 3 = (r_h+r_l) mod 3`.

Here `r_h,r_l` are in `{0,1,2}`. The low quotient word cannot overflow
64 bits; `check_algebra.py` enumerates the six possible remainder and
carry bounds. The signed result applies the original coordinate's sign
to the nonnegative quotient and remainder, preserving the generic
truncation-toward-zero contract. The existing digit adjustment then
computes the exact next Eisenstein coordinate.
