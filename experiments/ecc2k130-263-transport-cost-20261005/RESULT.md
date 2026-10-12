# Exact degree-263 route: transport stage cost

The checked Sage run completed **256/256** map evaluations on frozen ECC2K-130
points and matched every archived image or pullback. The independent parent
verifier had already reconstructed both maps and replayed all 512 public
target pairs and 128 base controls; this run timed a fixed subset of those
points. [`verification.json`](verification.json) checked the new receipt's
source, runtime, input hashes, IDs, sample arrays and summaries against that
earlier PASS. It does **not** independently reproduce the nanosecond timing.

| Operation on the verified degree-263 route | Primary target 0 | Median of 64 frozen calls | Range of 64 calls |
| --- | ---: | ---: | ---: |
| Source target → descendant, forward map | 45.721 ms | 43.888 ms | 32.262–68.136 ms |
| Descendant target → source, dual + isomorphism + `263⁻¹ mod r` | 42.531 ms | 39.853 ms | 30.682–62.475 ms |
| Source-base control → transported base, forward map | — | 48.895 ms | 32.955–90.082 ms |
| Native-base control → pullback base, inverse route | — | 43.300 ms | 29.873–101.466 ms |

Map construction and verification took **47.831 s** before these calls;
field construction took another **0.105 s**. Point decoding and equality
checks were outside each map interval. Peak process RSS was **324,747,264
bytes**. The primary one-target workload is `eee7f6ee5f6b`; the other 63
target points came from the separately named dormant control corpus
`f417f35ded09`. The exact unrounded samples, source/input/runtime SHA-256
values, and macOS arm64 host record are in [`result.json`](result.json).
The checked launcher runtime is [`runtime-info-r2.json`](runtime-info-r2.json).
An earlier same-input exploratory pass and its exact producer and verifier
sources are retained under [`development`](development/). Its 64-target
forward/inverse medians were 48.779/49.878 ms; the differing second-pass
medians illustrate host noise and cannot select a faster direction. Both
passes used the same verified Sage runtime manifest hash.
The auditor rejected a scratch result in which the primary forward duration
was changed by one nanosecond without changing the corresponding sample.

**Decision.** A future source-to-descendant native-base comparison must
charge a forward map of each new source target. The opposite direction must
charge the dual, isomorphism and subgroup inverse. Materializing either
transported or pullback factor base by this point-at-a-time Sage path is an
unmeasured full-base task, so the next solver should test an implicit base
representation or a batched/native map producer and report its construction
cost. The similar per-point forward and inverse medians are descriptive only;
this unisolated host and this Sage implementation do not establish a paired
performance ordering or a native-kernel bound. The two transported policy
pairs preserve exact sum membership by group isomorphism, while their
representation and transport costs can differ.

This is a **transport stage diagnostic**, not an IC online wall time. There
is still no natural W24/m6 PDP yield, verified relation rank, final matrix,
target logarithm, matched rho run, or speedup for `Q1420`. Its
`candidate_id` remains null. The next gate is a bounded, preregistered
ordinary-query W24/m6 PDP and novel-rank panel on the two mathematically
distinct base choices, with map and base preparation charged for any
transported implementation. The source and its transport, and the native
descendant and its pullback, should be paired as correctness controls rather
than four independent yield hypotheses.

From the repository root, reproduce the stage on a fresh output path with
the checked installed Sage build:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > /tmp/ecc2k130-263-transport-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/ecc2k130-263-transport-cost-20261005/measure.py --runtime-info /tmp/ecc2k130-263-transport-runtime.json --out /tmp/ecc2k130-263-transport-result.json
python3 experiments/ecc2k130-263-transport-cost-20261005/verify.py --result /tmp/ecc2k130-263-transport-result.json --runtime-info /tmp/ecc2k130-263-transport-runtime.json --out /tmp/ecc2k130-263-transport-audit.json
```

The measure script requires a checked runtime receipt and refuses to
overwrite an output. The verifier uses the explicit fresh result and runtime
paths, checks the executable source hashes and frozen input identities, and
links to the parent independent map replay. Fresh timings are exploratory
host observations, not expected to reproduce nanosecond-for-nanosecond.
