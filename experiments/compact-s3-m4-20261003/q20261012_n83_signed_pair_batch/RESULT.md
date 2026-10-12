# Q1502: paired-sign N83 scan removes 30% of batch multiplication calls

The native `PDP4hybrid` second-pair kernel now processes each base point
beside its negative. Both points have the same x coordinate, so the two
affine subtractions share one denominator inverse. On the exact
`EC1N83Ckb1h876c2921cb64` weight-at-most-five base, this changes the
source-level batch arithmetic from ten to seven multiplication calls per
signed point pair. Four target complements still scan all **B=30,977,592**
subgroup points each. The signed Frobenius quotient has **K=186,612**
columns; no isogeny is used.

| Fixed-first-pair cost, all four signs | Q1501 separate signs | Q1502 paired signs |
| --- | ---: | ---: |
| Candidate group additions | 123,910,368 | 123,910,368 |
| Batch multiplication calls, excluding inversion internals | 619,551,840 | **433,686,288** |
| Batch squaring calls, excluding inversion internals | 123,910,368 | 123,910,368 |
| Batch inversions, 512 candidates or pairs per batch | 242,016 | **121,008** |
| Full-scan median seconds, eight ordinary complements | 10.50 | **5.86** |

The multiplication saving is **30% = 0.515 bits** in this exact stage count.
All eight full scans completed over the same two ordinary public targets
(`2eb250a29072` and `394256b9f901`). Each Q1502 x-key checksum and hit
count matches the corresponding Q1501 full scan exactly; all eight observed
zero hits and zero exceptional denominators. The independent known-base-pair
control found a hit at the first signed pair and passed group replay. The
host has no isolation receipt, so the 1.25–3.83 observed per-cell wall
ratios and the median times are exploratory. They are not the charged
single-target online metric.

The Q1462 sampled conditional N131 weight-seven base has
B=118,153,819,312 and K=450,968,776. This paired-sign design would need
14B = **2^40.589 batch multiplication calls per fixed first pair**, plus
4B squarings, batch inversion internals, setup, and base membership work.
Under the intentionally optimistic arithmetic scenario that every full
four-sign scan yields one novel rank row, K rows would need
14BK = **2^69.338 batch multiplication calls**, 8.338 bits above an
abstract 2^61 multiplication-call reference. Failed first pairs and every
remaining pipeline phase increase that model cost. The complete N131
solve exponent remains null because the ordinary relation yield, rank
novelty, final matrix work, and target handling have not been measured for
this candidate.

This stage improvement leaves the number of scanned points unchanged.
The next solver step is an exact sublinear filter for second leaves, coupled
to a panel of distinct ordinary first pairs so that a measured relation
yield can be charged alongside the filter. At N53, the same paired kernel
can be checked on a complete relation as a transfer control before N131
work is projected.

## Reproduction

The [protocol](protocol.json) binds both Q1501 inputs and full rows, the
native source and binary, all eight N83 scans, the base file, batch size,
and time cap. The [build receipt](build_receipt.json) binds the compiler and
included field code. The [full rows](result.json),
[known-pair control](control_result.json), and [analysis](analysis.json)
preserve the exact matching and operation accounting. The commands are:

```sh
clang++ -O3 -std=c++17 -DECC2K83_ORBITS=186612 -DECC2K83_FAST_KEYER \
  experiments/compact-s3-m4-20261003/q20261012_n83_signed_pair_batch/native_signed.cpp \
  -o /Volumes/SSD990/llm/tmp/q1501-build/native_signed
python3 experiments/compact-s3-m4-20261003/q20261012_n83_signed_pair_batch/control.py
python3 experiments/compact-s3-m4-20261003/q20261012_n83_signed_pair_batch/analyze.py
```

`run.py` generated the frozen full-scan rows. It checks the Q1501 input and
baseline hashes before execution and verifies every checksum on completion.
