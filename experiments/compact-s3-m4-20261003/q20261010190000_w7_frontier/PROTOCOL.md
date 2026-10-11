# Q20261010190000: N131 weight-seven frontier screen

On the exact `EC1N131Ckb1h6816f880945e` N131 Koblitz curve, extend
Q1413's exact normal-x weight≤6 projected base with weight-seven supports.
Draw 250,000 distinct uniformly sampled seven-subsets of the 131 normal-basis
coordinates with seed 20261010190000. Classify rational x by
`Tr(x) = Tr(x^-1)` using the same checked field code as Q1303, and replay
64 sampled classifications with the independent curve-x lift. Store the
support/classification digest, source and input hashes, and a Wilson 95%
interval. This is a conditional base-size estimate; projection collisions
and exact weight-seven enumeration remain unmeasured.

Screen weights five through eight using exact Q1413 counts where available
and a half-rational mask model at seven and eight. For weight seven, use the
sample interval. Count four-point multisets per uniformly drawn nonidentity
subgroup target. Report two rank-supply models: all verified decompositions
per query (optimistic count bound) and at most one novel row per query.
Report `4K²` and `8K²` matrix-entry touches as explicit sparse-Wiedemann
planning models, not universal lower bounds or calibrated field operations.
Include no unmeasured costs as zero in a complete-solve estimate.

Freeze `PROTOCOL.md`, `screen.py`, Q1413 exact receipts, field/curve source,
and the subgroup order before sampling. Run `python3 screen.py freeze`,
`python3 screen.py run`, and `python3 screen.py check`. Outputs refuse
overwrite. This Q proposal has null IC candidate/run IDs and no isogeny.
