# Sage depth-one P-256 isogeny run

## Result

The SageMath 10.6 breadth-first search retained P-256 and six rational
horizontal neighbors reached by path degrees `3`, `5`, `11`, `11`, `13`, and
`13`. Every candidate has a verified explicit isogeny path, mapped generator,
kernel polynomial, and rational map in `candidates.json`. All seven curves have
geometric automorphism order 2; no exceptional automorphism was found.

The order-balanced benchmark found no statistically significant iteration-rate
improvement over P-256. All six paired 95% intervals contain `1.0`.

| Path degree | Mean iter/s | Paired speed vs P-256 | Paired 95% interval | Significant speedup |
| ---: | ---: | ---: | ---: | :---: |
| 1 (P-256) | 103,940 | 1.000 | 1.000–1.000 | no |
| 3 | 106,709 | 1.028 | 0.971–1.089 | no |
| 5 | 105,221 | 1.014 | 0.966–1.064 | no |
| 11 | 101,505 | 0.973 | 0.893–1.061 | no |
| 11 | 100,285 | 0.962 | 0.905–1.023 | no |
| 13 | 102,415 | 0.985 | 0.918–1.057 | no |
| 13 | 99,811 | 0.959 | 0.898–1.025 | no |

All measured rho states preserved their checked linear relation. The benchmark
used seven 1-second trials per curve, one warm-up per curve, identical seeds per
paired trial, and a rotating schedule that placed every curve in every timing
position once. Intervals are two-sided Student-t intervals on per-trial log2
rate ratios.

## Order-bias diagnostic

The original sequential benchmark was run both forward and in reverse. Its
apparent gains did not follow the curves: for example, one degree-11 neighbor
changed from `1.056x` to `0.968x`, and the degree-5 neighbor changed from
`1.026x` to `0.951x`. P-256 itself rose from 90,806 to 95,619 iterations/s when
its position moved from first to last. The corrected interleaved benchmark was
added in response; the two raw sequential reports are retained rather than
discarded.

## Cost accounting and claim limit

- Complete depth-one discovery took 0.995 seconds in this run.
- Individual retained paths had degree products 3, 5, 11, or 13 and were found
  within 0.241–0.995 seconds.
- The formulas needed to map both source points are retained, but per-key map
  evaluation was not timed.
- The host was not CPU-isolated, and this is reference Python rather than an
  optimized attack backend.

Accordingly, this run supports only the statement that no significant rho
iteration-rate improvement was detected in this six-neighbor depth-one sample.
It is not an exhaustive class-group search, does not rule out structure farther
away, and does not establish an end-to-end per-key attack speedup.

## Runtime

- SageMath image: `sagemath/sagemath:10.6`
- Image digest: `sha256:19995db6194f4a4bab18ce9a88556fd15b9ed5e916b4504fefe618a7796ddbdb`
- Candidate search parameters: `ells=3,5,11,13`, `depth=1`, `max_nodes=12`
- Corrected benchmark parameters: `seconds=1`, `trials=7`, `batch_width=64`,
  `table_size=16`, `warmup_seconds=0.1`
