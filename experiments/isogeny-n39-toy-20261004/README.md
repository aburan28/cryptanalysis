# N39 split-prime descent: paired factor-base stage control

This experiment is a tractable analogue of the verified ECC2K-130
degree-263 descent. It uses the ordinary Koblitz curve
`y²+xy=x³+1` over `GF(2^39)` in the polynomial basis
`t^39+t^4+1`. Its `F_(2^39)` trace is `1,481,485`, its group order is
`549,754,332,404 = 8,012 × 68,616,367`, and the chosen prime-order
subgroup has order `68,616,367`. The Frobenius-order conductor is
`24,569 = 79 × 311`. Degree 79 splits in the geometric endomorphism
order of discriminant `-7`; the `F_2` Frobenius polynomial `X²+X+2`
has roots 12 and 66 modulo 79. `F_(2^39)` acts as `-1` on the 79-torsion,
so the full 79-torsion is available over a **quadratic** extension.
That makes a checked descending map and dual inexpensive enough for a
held-out toy comparison. A nonhorizontal kernel changes the endomorphism
conductor from 1 to 79 by the ordinary-volcano theorem
([Sutherland, *Isogeny volcanoes*](https://arxiv.org/abs/1208.5370)).
The nearby N37 and N41 models are poorer route-construction controls:
their smallest Frobenius-conductor primes are 73 and 409, but the
corresponding torsion first becomes rational over extensions of degrees
18 and 408 of their base fields. N39 combines a 79-isogeny with a
quadratic torsion field and a 68,616,367-order subgroup large enough to
give a nontrivial four-summand hit panel.

The frozen [protocol](protocol.json) compares four exact 160-point bases:

| Policy | Curve and construction | Paired input |
| --- | --- | --- |
| `source` | First 160 usable cofactor-projected points from ascending polynomial-basis `x` values | Source public point |
| `transported` | Exact degree-79 images of `source` | Mapped public point |
| `descendant_native` | First 160 usable cofactor-projected points from the same `x` scan on the descendant model | Mapped public point |
| `pullback` | Native points returned to the source by the oriented dual and `79^{-1}` in the prime subgroup | Source public point |

The source/transported and native/pullback pairs must have identical
four-summand hit vectors: the maps are group isomorphisms on this prime
subgroup. Source versus native is the actual base-geometry comparison.
The 192 target points come from a fixed uniform, nonzero scalar sample;
fixture construction stays outside the lookup interval. The exact pair
index checks four summands, retains every miss, and independently sums
each returned witness. `verify_sage.py` reconstructs both checked maps,
replays all targets and accepted witnesses, and verifies the paired map
identities without trusting the run's recorded success flags.
The exact query panel has workload ID `c3894e3b0bcf` in
`workload.json`. This is a panel of ordinary **stage queries** for hit-rate
estimation, not a multi-target DLP solve or a replacement for the primary
one-target IC-versus-rho objective.

## Frozen result and decision

The one prespecified 160-point, 192-target panel completed in 406.45 s on
an unisolated local host. Both source and descendant-native bases found
**68/192 verified four-summand targets**. Their hit sets were different:
43 targets were source-only and 43 descendant-only, giving a paired
native-minus-source difference of **0.0 percentage points** with an
approximate 95% interval of **−9.47 to +9.47 points**. The transported
base matched the source hit vector exactly; the pullback base matched
the native vector exactly. The independent Sage replay verified all 192
targets, all accepted four-point witnesses, both maps, and both base
transport identities.

The source scan examined 299 raw `x` values and the native scan 311 to
obtain 160 distinct subgroup-usable points each. Their 12,880-pair tables
contained 12,874 and 12,880 distinct pair sums, respectively. Median
source lookup was 670.9 ms; median descendant lookup **including target
mapping** was 669.3 ms. Those times are exploratory and do not establish
a CPU speedup. All failed lookups contribute to the reported work per
verified hit. The prespecified 10-point hit-rate promotion gate failed,
so this particular first-`x`, cofactor-projected descendant-native policy
is deprioritized. The interval leaves smaller effects unresolved, and the
result says nothing about a different implicit codomain base.

These bases are **cofactor projected after the raw `x` scan**. Their final
coordinates do not satisfy a claimed implicit subspace constraint. This
is a group lookup control, not a summation-polynomial PDP, relation
collector, final matrix, target descent, or recovered logarithm. No
`IC1` candidate or IC-versus-rho speedup is issued. CPU timing ratios from
this local host are exploratory; the prespecified decision gate requires
a paired native hit advantage of at least 10 percentage points with a
positive approximate 95% lower bound and no more than twice the median
mapped-query stage cost. Even a passing stage gate would require a new
implicit PDP and complete one-target accounting before an attack claim.

The frozen result and decision are in `receipt-r1.json` and
`analysis-r1.json`. `runtime-info.json` records the checked Sage build.
From the repository root, verify the frozen artifacts and then use fresh
paths for any reruns:

```sh
./sage -python experiments/isogeny-n39-toy-20261004/verify_sage.py
python3 experiments/isogeny-n39-toy-20261004/freeze_workload.py --check
./sage --runtime-info > /tmp/n39-isogeny-runtime-info.json
./sage -python experiments/isogeny-n39-toy-20261004/run.py \
  --base-size 160 --targets 192 --out /tmp/n39-isogeny-replay.json
python3 experiments/isogeny-n39-toy-20261004/analyze.py \
  --receipt /tmp/n39-isogeny-replay.json --out /tmp/n39-isogeny-analysis.json
```
