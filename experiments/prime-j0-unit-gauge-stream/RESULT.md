# Held-out result: global unit gauge

The fresh 1,024-pair fixtures were frozen in commit `a7a0d903` after the
source and checker were frozen in `cf1b7830`. The expected digests come
from the independent Python affine group law in `make_inputs.py`; its
digest implementation was also checked against the previous fixture
before the new bytes were generated. Both the Release and UBSan panels
passed all serial trials and independently replayed every output.

| Curve | Arm | τ steps | Mixed adds | Rotations | Recodes | Pair scores | Nonzero gauges |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | joint | 13,953 | 7,783 | 5,121 | 2,042 | 0 | 0 |
| `glv-j0-32` | paired2 | 13,454 | 7,606 | 4,651 | 4,084 | 4,086 | 0 |
| `glv-j0-32` | paired2-gauge | 13,454 | 7,606 | 4,055 | 4,084 | 4,086 | 364 |
| `j0-56` | joint | 34,028 | 16,633 | 11,212 | 2,042 | 0 | 0 |
| `j0-56` | paired2 | 33,652 | 16,190 | 10,572 | 4,084 | 4,086 | 0 |
| `j0-56` | paired2-gauge | 33,652 | 16,190 | 9,188 | 4,084 | 4,086 | 505 |

Gauge selection saved 596 and 1,384 coordinate rotations relative to
paired2. Under the protocol's fixed `6*τ + 11*mixed_add + rotations`
model, those are reductions of about 0.35% of paired2 point work on
each curve. The prepared point object is 1,104 bytes for every arm;
preparation was two τ maps, ten doublings, eight mixed additions, and
one inversion. Both curves had 1,022 nonidentity outputs, hence 1,022
output inversions in every arm. The gauge arm did the same number of
recodings and pair scores as paired2, but it performed extra histogram
and gauge comparisons in ordinary integer code.

Local Release `online_ms` values for paired2 versus gauge were
`0.911,0.875` versus `0.870,0.919` on `glv-j0-32`, and
`1.832,1.853` versus `1.893,1.915` on `j0-56` in the frozen
six-trial order. These are exploratory measurements on an unverified
host; no controlled CPU ratio or speedup is claimed. The raw
`panel_local.json` and `panel_ubsan.json` preserve order, times,
failures, hashes, all counters, and `null` isolation receipts.

The small point-work saving does not justify automatic routing or
one-target rho integration yet. A later scheme could let the gauge vary
along the τ stream and charge transitions; that is a separate hypothesis
requiring a new fixture and correctness gate. Academic novelty is not
established by this experiment.
