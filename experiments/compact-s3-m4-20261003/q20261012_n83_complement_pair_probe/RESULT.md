# Q1501: exact N83 second-pair scan costs 2^26.885 additions per fixed first pair

The native `PDP4hybrid` probe takes a verified Q1497 first pair, lifts and
cofactor-projects its two x coordinates, and forms the four signed complements
of the public target. For each complement it scans every point in the exact
N83 factor base, computes the remaining point by batched affine subtraction,
and tests its x coordinate against all signed Frobenius base orbits. Both
signs of every base point are included, so an x-orbit hit is an exact base
membership hit. A detected hit is also replayed with the curve group law.

The curve is `EC1N83Ckb1h876c2921cb64` over the declared degree-83 type-II
normal basis, with subgroup order 2,417,851,639,230,796,216,685,689.
The weight-at-most-five projected base has **B=30,977,592** actual subgroup
points and **K=186,612** signed Frobenius columns. The two ordinary public
points have workload IDs `2eb250a29072` and `394256b9f901`. The experiment
uses proposal ID Q1501 and null candidate/run IDs because relation collection,
final matrix solving, and target descent are not fixed as one IC pipeline.

| Target | Signed complements completed | Base points scanned per complement | Second-pair hits | Scan seconds, range |
| --- | ---: | ---: | ---: | ---: |
| selected | 4 | 30,977,592 | 0 | 7.54–12.03 |
| holdout | 4 | 30,977,592 | 0 | 7.44–20.19 |

All eight runs completed without exceptional additions. Their scan-time
median was 10.50 seconds. These CPU times are exploratory because the host
has no isolation receipt. The exact counted stage is **123,910,368 =
2^26.885 group-add attempts per fixed first pair**, charging all four sign
choices. With no exceptional additions, the batch kernel also makes
619,551,840 field multiplication calls, 123,910,368 field squaring calls,
and 242,016 field inversions per first pair; the inversion internals and
base-membership bit operations are additional work. The 512-element batch
had a 0.208-second median per million candidates in the bounded panel,
compared with 0.216 seconds for the 2048-element batch. Both sizes produced
identical complement checksums on each frozen input.

An independent Python control constructed a target as the sum of two
enumerated base representatives. The native scan found its second leaf at
the first position and passed group replay. The eight ordinary zero-hit rows
therefore give complete results for **these two fixed first pairs**; they do
not determine the ordinary first-pair distribution or complete four-summand
relation rate.

For the separate Q1462 **sampled conditional** N131 weight-seven base,
B=118,153,819,312 and K=450,968,776. Applying this direct-scan design
would cost 4B = **2^38.782 group additions per fixed first pair**. The
optimistic arithmetic scenario of exactly one such scan yielding each novel
rank row costs 4BK = **2^67.530 group additions**, 6.530 bits above an
abstract 2^61 group-addition reference before setup, failed first pairs,
matrix work, or target handling. The scenario assumes every scan succeeds;
Q1501 measured zero hits in eight complete scans. It is a conditional
component model, not a complete N131 solve estimate. The complete solve
exponent and gap in a common calibrated unit remain null.

The next experiment should sample **distinct** first pairs on ordinary N83
points and hand each to this exact subsolver, recording cost and relation
yield together. A useful solver change must reduce the second-pair work
below the linear-in-B scan or produce multiple independent rank rows per
query; tuning batch size alone did not change the operation count. A separate
N53 control can check the same handoff end to end on its exact base.

## Reproduction

The [input freeze](frozen_inputs.json) binds the first-pair receipts, public
targets, base file, preparation source, and native source. The
[build receipt](build_receipt.json) binds the compiler flags, included native
source, field header, and binary. The
[full protocol](full_protocol.json) binds the binary, full B scan, all eight
inputs, batch size, and per-cell timeout. The [bounded rows](result.json),
[full rows](full_result.json), [control](control_result.json), and
[analysis](analysis.json) retain statuses, exact counts, checksums, and
exploratory timing. On ARM64 macOS, build and run with:

```sh
mkdir -p /Volumes/SSD990/llm/tmp/q1501-build
clang++ -O3 -std=c++17 -DECC2K83_ORBITS=186612 -DECC2K83_FAST_KEYER \
  experiments/compact-s3-m4-20261003/q20261012_n83_complement_pair_probe/native_probe.cpp \
  -o /Volumes/SSD990/llm/tmp/q1501-build/native_probe
python3 experiments/compact-s3-m4-20261003/q20261012_n83_complement_pair_probe/control.py
python3 experiments/compact-s3-m4-20261003/q20261012_n83_complement_pair_probe/analyze.py
```

The measured `run.py` and `full_scan.py` commands created the bounded and
full rows. They refuse changed frozen inputs. The source includes
`q20261012_native_rational_guard/native_n83_pairs.cpp` and its pinned
`eccF83.h`; the Q1501 loader reads this repository's 21-byte packed keys.
