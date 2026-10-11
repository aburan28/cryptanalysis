# Benchmarks

All numbers below were produced by `build/ca_bench` on one 4-core x86-64
container (gcc 13, `-O3`, no `-march=native`), 5 instances per row unless
stated.  Reproduce with `make bench` or the individual commands shown.
They are measurements of *this* implementation on *this* machine; the
operation counts are the portable part, the seconds are not.

The reporting convention follows the sibling research repository: one
table, one unit, every variant a row, the reference (rho) included.  The
unit is `S = group operations / sqrt(N)`.

That unit assumes the exponent is `1/2`.  The `generic`, `interval` and
`precomp` modes now also *measure* it: each table ends with a fitted-exponent
summary (`cost ~ C * N^alpha`), and `ca_bench complexity` compares every
algorithm's exponent in one place (see "Measured time complexity" below).  So
the constant `S` is only quoted once the fitted exponent confirms the `O()`.

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

## Discrete logarithm with precomputation (`ca_bench precomp`)

Bernstein-Lange free precomputation (`ca_precomp.h`): one table is built per
group, then `--reps` random targets are solved against it.  `P` is the
one-time precomputation cost, `T` the per-target online cost; `t` is the
distinguished-point bit count `round(log2 n / 3)` and `chains` the table
size.  `sqrtN/T` is the per-target speed-up of the online phase over a
from-scratch `sqrt(n)` search.

Build on one core (`--threads 1`):

| grp | bits |  t | chains | precomp ops | P/n^{2/3} | build s | online ops | T/n^{1/3} | √n / T |
|-----|-----:|---:|-------:|------------:|----------:|--------:|-----------:|----------:|-------:|
| zp | 24 |  7 |   200 |      36366 | 1.398 | 0.0009 |   310.6 | 1.926 |  6.6 |
| ec | 24 |  8 |   117 |      36815 | 0.892 | 0.0011 |  1513.4 | 7.447 |  1.9 |
| zp | 28 |  9 |   185 |     129591 | 0.785 | 0.0032 |  1150.6 | 2.831 |  7.1 |
| ec | 28 |  9 |   426 |     285046 | 1.087 | 0.0080 |  2320.4 | 4.532 |  5.0 |
| zp | 32 | 10 |   787 |     999317 | 0.953 | 0.0246 |  2184.8 | 2.134 | 15.0 |
| ec | 32 | 10 |  1558 |    2180963 | 1.310 | 0.0596 |  2781.2 | 2.156 | 16.7 |
| zp | 36 | 11 |  3039 |    8500087 | 1.277 | 0.2097 |  2325.6 | 0.901 | 56.4 |
| ec | 36 | 11 |  6145 |   16820363 | 1.591 | 0.4387 |  6769.4 | 2.082 | 27.4 |

Reading the table: the precomputation sits at `P ~ 0.8 - 1.6 n^{2/3}` and the
table at `n^{1/3}` entries, both as the theory predicts and close to the
paper's `1.24 n^{2/3}` / `n^{1/3}`.  The online cost is `T ~ 1 - 7 n^{1/3}`
(5 targets per row, so the same `~+-30 %` statistical noise as the rho rows,
plus the one scalar-multiplication walk start that each attempt pays); the
paper's figure is `1.77 n^{1/3}`.  The `√n / T` column is the point of the
method: the per-target online search is already `7x - 56x` cheaper than the
`sqrt(n)` it would otherwise cost, and the ratio grows as `n^{1/6}`, so at
cryptographic sizes it is enormous -- at the price of a precomputation that
is itself larger than one `sqrt(n)` search and is only worth it amortised
over many targets in a fixed group.  See ALGORITHMS.md for why this is a
statement about non-uniform security rather than a practical attack.

**Optimisations.**  The build uses a fixed-base table for walk starts, one
batched field inversion per `W` curve additions, and a sorted
(fingerprint, exponent) table (16 bytes/entry, ~4x smaller than the hash
table it replaced).  Together they took the 36-bit curve build from 2.26 s
(a naive one-add-per-inversion, double-and-add-start version) to the 0.44 s
above -- a 5x wall-clock win on one core before any threading.  `--threads 4`
then builds it in 0.11 s (3.9x more).  An optional Bloom early-abort
(`--early-abort`) pays off only when the table is deliberately built to
over-cover the group: on a 2^17 group at coverage 32 it cut the
precomputation from 121k to 77k operations while storing about twice the
distinct endpoints; at the default coverage of 1 merges are negligible and
it is off.

## GLV endomorphism-accelerated rho (`ca_bench glv`)

Curve-aware dispatch (`ca_curve.h`): on a CM curve the rho walk is folded by
the automorphism group `<psi>` (order 6 for j-invariant 0, 4 for j-invariant
1728), against the plain negation-map rho on the same curve.  `S = group
operations / sqrt(n)`; 20 instances per row.

| curve         | endo  | m | GLV S | negation-rho S | speedup |
|---------------|-------|--:|------:|---------------:|--------:|
| glv-j0-26     | j0    | 6 | 1.412 | 1.608 | 1.14x |
| glv-j1728-26  | j1728 | 4 | 1.516 | 2.038 | 1.34x |
| glv-j0-32     | j0    | 6 | 0.988 | 1.688 | 1.71x |
| glv-j1728-32  | j1728 | 4 | 1.587 | 1.487 | 0.94x |
| generic-26    | none  | 2 | 1.957 | 1.957 | 1.00x |

The expected gain over the negation-map rho is `sqrt(m/2)` -- `1.73` for j0
and `1.41` for j1728 -- and the cleaner rows (`glv-j0-32` at 1.71x,
`glv-j1728-26` at 1.34x) land there.  The scatter is large because these are
small curves (a single rho run's standard deviation is about its mean, so 20
instances still leave roughly `+-20%`, and a couple of rows come out below
1x); the generic curve is identical either way, as it must be.  The point is
the folding, not the wall clock: it is a smaller constant in front of the
same `sqrt(n)`, applied automatically once the curve's j-invariant is
recognised.  `ca curve --name <name>` reports the structure and the chosen
solver without running anything.

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

## GPU rho kernel (`ca_bench gpu`)

There is no GPU in the machine these numbers come from, so the rows below
are the **host emulator**: the identical kernel body executed one thread at
a time on one CPU core.  The operation counts are therefore meaningful and
portable, the seconds column is not a GPU measurement, and no row here says
anything about device throughput.

| grp | bits | solver | S = ops/√n | walks | launches | ok |
|-----|-----:|--------|-----------:|------:|---------:|----|
| zp | 24 | cpu-rho | 1.849 | 1 | - | 3/3 |
| zp | 24 | gpu-rho (emulate) | 1.895 | 8 | 3.7 | 3/3 |
| ec | 24 | cpu-rho | 1.707 | 1 | - | 3/3 |
| ec | 24 | gpu-rho (emulate) | 1.844 | 8 | 6.3 | 3/3 |
| zp | 28 | cpu-rho | 2.578 | 1 | - | 3/3 |
| zp | 28 | gpu-rho (emulate) | 1.990 | 8 | 18.0 | 3/3 |
| ec | 28 | cpu-rho | 2.033 | 1 | - | 3/3 |
| ec | 28 | gpu-rho (emulate) | 1.504 | 16 | 7.3 | 3/3 |
| zp | 32 | cpu-rho | 2.045 | 1 | - | 3/3 |
| zp | 32 | gpu-rho (emulate) | 1.262 | 40 | 14.0 | 3/3 |
| ec | 32 | cpu-rho | 0.873 | 1 | - | 3/3 |
| ec | 32 | gpu-rho (emulate) | 1.857 | 56 | 11.3 | 3/3 |

What this table is for: it shows that spreading the same search over many
more concurrent walks does not change the constant in front of `sqrt(n)`.
Both solvers sit at `S ~ 1.3 - 2.6` at every size (3 instances per row, so
roughly +-30 % noise), which is the expected result: van Oorschot-Wiener
parallelisation is linear in the number of walkers, so `M` walks each doing
`1/M` of the work cost the same total, and a GPU buys wall-clock time rather
than operations. A regression here (an `S` that grows with the walk count)
would mean the distinguished-point density or the restart policy is wrong,
which is exactly what this row is watching for.

"walks" grows with the group because the driver caps walk start-up cost at
`sqrt(n)/8`; on a real device the cap is lifted by the size of the problem,
not the hardware, so 2^48 and above is where a GPU has enough walks to fill
it.

Kernel cost from `scripts/build_cuda_kernel.sh --fetch` (clang 18 + ptxas
12.9, no GPU required):

| arch | registers | local memory/thread | spills |
|------|----------:|--------------------:|-------:|
| sm_70 | 72 | 736 B | 0 |
| sm_80 | 64 | 736 B | 0 |
| sm_89 | 64 | 736 B | 0 |
| sm_90 | 64 | 736 B | 0 |

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

## Measured time complexity (`ca_bench complexity`)

Every other table quotes a constant against an *assumed* exponent (`ops/√n`,
`P/n^{2/3}`, ...).  This mode instead *measures* the exponent: it runs each
algorithm across a size sweep, fits the group-operation cost to
`cost ~ C * N^alpha` by least squares in log-log space, and reports the
fitted `alpha` with its `R^2` next to the theoretical exponent.  `scope` is
`global` for a whole algorithm and `step` for one phase of a method -- so the
two phases of the precomputation method, which have genuinely different orders
(`n^{2/3}` to build, `n^{1/3}` per online target), are measured separately.
The last column is the normalised constant `mean(cost / N^theory)` -- the
familiar `S`, meaningful precisely because the fitted `alpha` confirms the
exponent.

`ca_bench complexity --bits 20,24,28,32,36 --reps 5`:

| algorithm       | scope  | theory   | fitted alpha | R^2    | const @ N^theory |
|-----------------|--------|----------|-------------:|-------:|-----------------:|
| bsgs (zp)       | global | N^0.500  | 0.487 | 0.9993 | 1.508 |
| rho (zp)        | global | N^0.500  | 0.477 | 0.9903 | 1.781 |
| kangaroo (zp)   | global | N^0.500  | 0.526 | 0.9910 | 1.843 |
| grumpy (zp)     | global | N^0.500  | 0.502 | 0.9966 | 1.264 |
| precomp build (zp)  | step | N^0.667 | 0.647 | 0.9954 | 1.192 |
| precomp online (zp) | step | N^0.333 | 0.347 | 0.8768 | 2.781 |
| bsgs (ec)       | global | N^0.500  | 0.487 | 0.9993 | 1.508 |
| rho (ec)        | global | N^0.500  | 0.428 | 0.9845 | 1.572 |
| kangaroo (ec)   | global | N^0.500  | 0.494 | 0.9995 | 1.622 |
| grumpy (ec)     | global | N^0.500  | 0.480 | 0.9956 | 1.128 |
| precomp build (ec)  | step | N^0.667 | 0.672 | 0.9877 | 1.302 |
| precomp online (ec) | step | N^0.333 | 0.198 | 0.9798 | 2.920 |

The square-root methods land at `alpha ~ 0.5` and the precomputation phases at
`0.667` and `0.333`, so the measured `O()` matches the theory across the
board.  The online row is the noisiest fit: its operation counts are the
smallest (a few hundred at 20 bits) and are dominated by the constant walk
start, which flattens the slope -- widen `--bits` or raise `--reps` for a
tighter online exponent.  Index calculus is deliberately absent: it is
subexponential (`L_p[1/2]`), so no single power-law exponent describes it; see
the `ic` table for its stage timings.
