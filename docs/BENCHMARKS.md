# Benchmarks

All numbers below were produced by `build/ca_bench` on one 4-core x86-64
container (gcc 13, `-O3`, no `-march=native`), 5 instances per row unless
stated.  Reproduce with `make bench` or the individual commands shown.
They are measurements of *this* implementation on *this* machine; the
operation counts are the portable part, the seconds are not.

The reporting convention follows the sibling research repository: one
table, one unit, every variant a row, the reference (rho) included.  The
unit is `S = group operations / sqrt(N)`.

## Raw group operation throughput (`ca_bench ops`)

| operation                              | Mops/s | ns/op |
|----------------------------------------|-------:|------:|
| `Z_p^*` 61-bit Montgomery multiply     |  169.4 |   5.9 |
| `E(F_p)` 60-bit affine add, 1 inversion|   4.31 | 232.2 |
| `E(F_p)` 60-bit affine add, batch 256  |  45.88 |  21.8 |

The batched addition (Montgomery's simultaneous inversion) is what the
rho and kangaroo walks use; it is 10.6x faster than a private inversion
per addition.

## Whole-group discrete logarithm (`ca_bench generic --threads 4`)

Prime-order groups: `Z_p^*` subgroups of safe primes and prime-order
curves.  `rho-T` uses 4 threads; `S` counts all threads' operations.

| grp | bits | algorithm | S = ops/√n | seconds | ok  |
|-----|-----:|-----------|-----------:|--------:|-----|
| zp  |  24 | bsgs      | 1.496 | 0.0001 | 5/5 |
| zp  |  24 | rho-1     | 2.066 | 0.0001 | 5/5 |
| zp  |  24 | rho-T     | 1.960 | 0.0005 | 5/5 |
| zp  |  24 | kangaroo  | 1.751 | 0.0001 | 5/5 |
| zp  |  24 | grumpy    | 1.242 | 0.0000 | 5/5 |
| ec  |  24 | bsgs      | 1.496 | 0.0006 | 5/5 |
| ec  |  24 | rho-1     | 1.603 | 0.0004 | 5/5 |
| ec  |  24 | rho-T     | 2.290 | 0.0007 | 5/5 |
| ec  |  24 | kangaroo  | 1.886 | 0.0003 | 5/5 |
| ec  |  24 | grumpy    | 1.211 | 0.0004 | 5/5 |
| zp  |  32 | bsgs      | 1.575 | 0.0018 | 5/5 |
| zp  |  32 | rho-1     | 1.256 | 0.0008 | 5/5 |
| zp  |  32 | rho-T     | 1.575 | 0.0023 | 5/5 |
| zp  |  32 | kangaroo  | 1.412 | 0.0004 | 5/5 |
| zp  |  32 | grumpy    | 1.365 | 0.0014 | 5/5 |
| ec  |  32 | bsgs      | 1.575 | 0.0129 | 5/5 |
| ec  |  32 | rho-1     | 0.791 | 0.0027 | 5/5 |
| ec  |  32 | rho-T     | 1.159 | 0.0033 | 5/5 |
| ec  |  32 | kangaroo  | 2.174 | 0.0039 | 5/5 |
| ec  |  32 | grumpy    | 1.514 | 0.0143 | 5/5 |
| zp  |  36 | bsgs      | 1.441 | 0.0107 | 5/5 |
| zp  |  36 | rho-1     | 1.563 | 0.0043 | 5/5 |
| zp  |  36 | rho-T     | 1.562 | 0.0044 | 5/5 |
| zp  |  36 | kangaroo  | 1.691 | 0.0020 | 5/5 |
| zp  |  36 | grumpy    | 1.351 | 0.0121 | 5/5 |
| ec  |  36 | bsgs      | 1.441 | 0.0663 | 5/5 |
| ec  |  36 | rho-1     | 1.283 | 0.0173 | 5/5 |
| ec  |  36 | rho-T     | 1.913 | 0.0469 | 5/5 |
| ec  |  36 | kangaroo  | 1.768 | 0.0112 | 5/5 |
| ec  |  36 | grumpy    | 1.413 | 0.0785 | 5/5 |
| zp  |  40 | bsgs      | 1.573 | 0.1373 | 5/5 |
| zp  |  40 | rho-1     | 0.887 | 0.0112 | 5/5 |
| zp  |  40 | rho-T     | 1.729 | 0.0084 | 5/5 |
| zp  |  40 | kangaroo  | 1.795 | 0.0087 | 5/5 |
| zp  |  40 | grumpy    | 1.393 | 0.0924 | 5/5 |
| ec  |  40 | bsgs      | 1.573 | 0.3674 | 5/5 |
| ec  |  40 | rho-1     | 1.713 | 0.0762 | 5/5 |
| ec  |  40 | rho-T     | 1.421 | 0.0543 | 5/5 |
| ec  |  40 | kangaroo  | 1.220 | 0.0339 | 5/5 |
| ec  |  40 | grumpy    | 1.251 | 0.4176 | 5/5 |

Reading the table: with 5 instances per row the rho and kangaroo rows
carry about +-25 % statistical noise (the standard deviation of one run
is about half its mean), so the honest summary is "rho, kangaroo and
grumpy giants all sit at `S ~ 1.2 - 1.8`, BSGS at 1.5, as theory says".
The wall-clock column shows the structural facts: table-based methods
(BSGS, grumpy) are memory-bound and slow down per operation as the table
grows, rho stays at 40 - 100 Mops/s in `Z_p^*` and 10 - 20 Mops/s on
curves (batched additions), and kangaroo is the fastest per operation
because it stores almost nothing.

## Interval discrete logarithm (`ca_bench interval`)

Width `2^w` inside a `~2^60` (`Z_p^*`) or `~2^56` (curve) prime-order group.

| grp | width | algorithm | S = ops/√w | seconds | ok  |
|-----|-------|-----------|-----------:|--------:|-----|
| zp  | 2^24  | bsgs      | 1.658 | 0.0002 | 5/5 |
| zp  | 2^24  | kangaroo  | 1.628 | 0.0001 | 5/5 |
| zp  | 2^24  | grumpy    | 2.205 | 0.0005 | 5/5 |
| ec  | 2^24  | bsgs      | 1.657 | 0.0016 | 5/5 |
| ec  | 2^24  | kangaroo  | 2.842 | 0.0009 | 5/5 |
| ec  | 2^24  | grumpy    | 2.203 | 0.0022 | 5/5 |
| zp  | 2^28  | bsgs      | 1.613 | 0.0006 | 5/5 |
| zp  | 2^28  | kangaroo  | 1.541 | 0.0002 | 5/5 |
| zp  | 2^28  | grumpy    | 1.902 | 0.0008 | 5/5 |
| ec  | 2^28  | bsgs      | 1.612 | 0.0064 | 5/5 |
| ec  | 2^28  | kangaroo  | 2.416 | 0.0019 | 5/5 |
| ec  | 2^28  | grumpy    | 1.902 | 0.0075 | 5/5 |
| zp  | 2^32  | bsgs      | 1.673 | 0.0042 | 5/5 |
| zp  | 2^32  | kangaroo  | 1.983 | 0.0011 | 5/5 |
| zp  | 2^32  | grumpy    | 1.927 | 0.0052 | 5/5 |
| ec  | 2^32  | bsgs      | 1.673 | 0.0289 | 5/5 |
| ec  | 2^32  | kangaroo  | 1.899 | 0.0055 | 5/5 |
| ec  | 2^32  | grumpy    | 1.927 | 0.0348 | 5/5 |
| zp  | 2^36  | bsgs      | 1.600 | 0.0245 | 5/5 |
| zp  | 2^36  | kangaroo  | 2.345 | 0.0062 | 5/5 |
| zp  | 2^36  | grumpy    | 2.034 | 0.0433 | 5/5 |
| ec  | 2^36  | bsgs      | 1.600 | 0.1376 | 5/5 |
| ec  | 2^36  | kangaroo  | 2.002 | 0.0185 | 5/5 |
| ec  | 2^36  | grumpy    | 2.034 | 0.1614 | 5/5 |

A separate 400-instance run of grumpy giants (see ALGORITHMS.md) gives
`S = 1.78` for intervals and `1.18` for whole groups; the 5-instance rows
above scatter around those values.

## Index calculus in `Z_p^*` (`ca_bench ic --threads 4`)

Safe primes `p = 2q + 1`, linear sieve, default `(B, C)`.  "rho ops ref"
is `1.3 sqrt(q)`, the cost of rho in the order-`q` subgroup.

| bits | p | fb | unknowns | rels | sieve s | linalg s | precomp s | log s | tries | rho ops ref |
|-----:|---|---:|---------:|-----:|--------:|---------:|----------:|------:|------:|------------:|
| 32 | 2147483783 | 53 | 354 | 1290 | 0.001 | 0.030 | 0.031 | 0.000 | 147 | 4.3e4 |
| 40 | 549755815199 | 125 | 926 | 1744 | 0.001 | 0.085 | 0.086 | 0.000 | 289 | 6.8e5 |
| 48 | 140737488356903 | 303 | 2504 | 3657 | 0.003 | 0.311 | 0.315 | 0.000 | 412 | 1.1e7 |
| 56 | 36028797018970703 | 669 | 6270 | 7683 | 0.007 | 1.262 | 1.270 | 0.001 | 433 | 1.7e8 |

The sieve is essentially free at these sizes; the cost is the Lanczos
solve, which grows as (unknowns)^2.  Rho at 56 bits costs `1.7e8`
operations, about 1.5 s at the `Z_p^*` rate above, so the crossover with
rho on this machine is near 56 bits and index calculus wins clearly above
it.  Individual logarithms are negligible (a few hundred trial divisions).

## Cheon's attack (`ca_bench cheon`)

Groups of prime order `p` where `p - 1` has a divisor `d ~ sqrt(p)`,
attack with `d = ca_cheon_best_divisor(p)`, compared with rho on the same
instance.

| bits | p | d | Cheon exps | Cheon ops | rho ops | speedup |
|-----:|---|--:|-----------:|----------:|--------:|--------:|
| 32 | 4295294977 | 65536 | 826 | 37602 | 70533 | 1.9x |
| 40 | 1099516870657 | 1048576 | 3007 | 171491 | 727779 | 4.2x |
| 48 | 281475127705601 | 16777216 | 10908 | 762010 | 14168905 | 18.6x |

Each Cheon step is an exponentiation (`~1.5 log2 p` operations), so the
advantage in *group operations* is `sqrt(p) / (2 (sqrt((p-1)/d) + sqrt(d)) * 1.5 log2 p)`
and grows with the size of `p`; in *steps* the reduction is
`sqrt(p) / 2 p^{1/4}`, i.e. 30x at 32 bits and 480x at 48 bits.
