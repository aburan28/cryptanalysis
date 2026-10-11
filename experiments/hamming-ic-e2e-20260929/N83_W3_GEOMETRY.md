# N83 transfer gate for the N53 weight-three four-sum method

The N53 root-index holdout completed all 512 points in its prospective panel.
This N83 experiment measures the **same weight-three normal-basis factor-base
construction and four-summand support**, on the exact N83 Koblitz subgroup.
It is an exact base-geometry result, not an N83 root-index query, IC DLP, or
CPU speedup measurement. `candidate_id` remains `null` because the N83 PDP,
relation collection, final matrix solver, and target recovery are unbuilt.

## Exact instance and measured base

The field is polynomial-basis `GF(2^83)` with modulus
`u^83+u^7+u^4+u^2+1`; the curve is `y^2+xy=x^3+1`, with subgroup order
`r=2417851639230796216685689`, cofactor 4, and curve ID
`EC1N83Ckb1h2bcb59d56ad6`. This ID hashes the **polynomial-basis** field,
exact curve, and encoded generator; it differs from the N83 type-II-ONB ID
used by other studies. The first normal element in ascending
polynomial-bit order is `3`, as in the N53 study. For each Frobenius orbit of
three-coordinate masks, the producer tests rationality, lifts one raw curve
point, applies `[4]`, and expands its signed-Frobenius orbit. It uses no known
factor-base logarithms.

| Quantity | Exact result |
| --- | ---: |
| Nominal weight-three masks | 91,881 |
| Mask Frobenius orbits | 1,107 |
| Rational / nonrational x orbits | 539 / 568 |
| Distinct usable subgroup points before folding, `B` | **89,474** |
| Effective signed-Frobenius columns | **539** |
| Four-point multisets with repetition | 2,670,578,165,974,428,325 |
| Prime subgroup elements | 2,417,851,639,230,796,216,685,689 |
| Maximum fraction of uniformly selected subgroup points with a four-sum | **0.000001104525242**, or 0.000110453% |

The support fraction is a **rigorous upper bound**, not a Poisson estimate:
each four-point multiset has one group sum, so at most
`C(B+3,4)` subgroup elements can be represented. Collisions can only reduce
coverage. For 512 independent uniform subgroup points, the expected number
with any such decomposition is at most 0.000565517, and the probability of
even one is at most the same number by the union bound. A particular fixed
point may still be representable. The N53 mean was about 596 four-point
multisets per subgroup element; the N83 support ceiling is about 540 million
times smaller. Enlarging the root index or searching more orientations
cannot change this base's mathematical four-sum support.

The checked-Sage [producer result](runs/n83_w3_geometry_v2/geometry.json)
enumerated all 1,107 mask orbits, retained the exact
[representatives](runs/n83_w3_geometry_v2/representatives.json), and measured
28.850 seconds for base enumeration and orbit expansion with 286.9 MB peak
RSS. These Mac timings are exploratory and make no CPU speedup claim. The
separate checked-Sage [replay](runs/n83_w3_geometry_v2/sage_replay.json)
used Sage's `lift_x` instead of the producer's half-trace lift and a matrix
rank check instead of bit elimination. It re-enumerated the complete base,
checked every projected representative in the subgroup, matched both full
point-set SHA-256 digests and the representative set, and recomputed the
exact support numerator and polynomial-basis curve ID. The producer and replay each saved checked Sage
runtime identity before starting.

An earlier local attempt assigned the type-II-ONB curve ID to polynomial
coordinates. It is retained with an explicit
[identity rejection](runs/n83_w3_geometry_v1/IDENTITY_REJECTION.json); none
of its records count as accepted N83 measurements. The corrected v2 run
recomputed the field/curve hash and independently checked its encoded
generator in the prime subgroup before accepting the unchanged geometry.

## Decision

The N53 weight-three, four-summand method does **not** transfer as an
ordinary-target N83 panel: even an ideal decomposition oracle has at most
the support fraction above on uniformly selected subgroup points. Launching
the N53-style 512-point root-index query panel on this base would therefore
measure mostly the known geometric coverage failure. An N83 study needs a
different base or summand count, with its own exact identity and planted
correctness gate, before ordinary queries and complete DLP accounting. This
result makes no claim about other N83 bases or their algorithms.

## Reproduce

From a checkout containing this experiment, use the repository's checked
Sage launcher. Use a fresh output directory for a new run:

```sh
mkdir -p /private/tmp/new-n83-w3-geometry
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /private/tmp/new-n83-w3-geometry/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_measure_n83_w3_geometry.py /private/tmp/new-n83-w3-geometry
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /private/tmp/new-n83-w3-geometry/sage_runtime_info_replay.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/hamming-ic-e2e-20260929/sage_replay_n83_w3_geometry.py /private/tmp/new-n83-w3-geometry
```

The producer writes `started.json` and progress before its final geometry
receipt. Missing or failed output remains a failed stage, never a zero-cost
or successful point-decomposition row.
