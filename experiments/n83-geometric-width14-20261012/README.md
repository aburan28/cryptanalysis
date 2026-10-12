# Shifted N83 geometric width-14 factor base

The exact shifted width-14 base on `EC1N83Ckb1h876c2921cb64` has **8,261
signed-Frobenius columns and 1,371,326 usable subgroup points** before
folding. It contains all rational x-coordinate seeds in
`gamma_82 + span(gamma_1,...,gamma_14)`, projects each lift by cofactor
four, and closes under sign and 83 Frobenius powers. The distinct
five-subset first moment on a uniform subgroup target is
`16714.349889115683473202508972062400244932974207624`; the analogous
width-13 count was `518.85136952457687690245981676292458366701831687528`.
These are exact combinatorial counts for the two bases, not measured
ordinary-query relation rates.

The [frontier receipt](frontier.json) records all 16,384 x seeds, 8,262
rational lifts, one duplicate folded orbit, the sorted canonical key file,
source hashes, and exact payload arithmetic. The full 83K² root index at
this width has 5,664,262,043 states and a 181,256,385,376-byte packed-root
payload; the current five-summand SAT stage does not allocate that index.
The [independent Sage replay](independent_sage_replay.json) checked all
seeds, cofactor projections, subgroup membership, signed Frobenius orbit
sizes, and key-file bytes in a separate polynomial-basis field. It
returned `PASS`.

The checked [Sage runtime](sage_runtime_info.json) was saved before both
producer jobs. In a fresh experiment directory, run through the repository
launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-width14-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width14-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-width14-20261012/verify_sage.py
```

The stage retains `candidate_id: null` until a complete method, measured
ordinary relations, rank, target recovery, and a paired same-point rho run
are available. Local scan and replay timings are exploratory.
