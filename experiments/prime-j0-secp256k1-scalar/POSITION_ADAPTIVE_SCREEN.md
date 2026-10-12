# Per-position τ digit-choice screen

`position_adaptive.py` explored choosing the width-four residue digit or
its width-three fallback **at each nonzero position**, instead of fixing
one seed mask for the full scalar. It used a beam of 64 paths, ranked by
prepared-seed cost, digit count, and an estimated remaining norm. Final
paths were scored with the exact one-use model from `hybrid_subset.py`;
the existing width-four path was always available as a fallback. Every
returned expansion reconstructed its input ring element exactly.

The retrospective screen reused the 64 cases in
`hybrid-holdout-result.json`; `position-adaptive-training-result.json`
retains each case and the source hash. This is training evidence, not a
new held-out comparison. It expanded **549,377** path states to obtain a
total modeled score of **84,336 `M+S`** versus **85,433** for width four:
17.14 saved per scalar, excluding all search cost. On those same cases,
the already-tested 64-mask selector saved 22.28 per scalar. The beam
beat that mask oracle on 12 cases, tied 12, and was worse on 40; its
aggregate score was 329 units worse. The beam is therefore **not
promoted**, and no fresh Sage workload was launched for it.

This screen does not rule out an exact or better-guided per-position
optimizer. It does rule out the present 64-path heuristic as a useful
complete-operation candidate: it explores over half a million states
yet fails to match the earlier mask selector's arithmetic score. Neither
CPU speedup nor academic novelty has been established.
