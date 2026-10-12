# Fixed-memory tau/rho cover by cycle pruning and exchanges

This construction reduces rho-map use at the same 67,338-seed budget as the
swapped radix-1024 cover. The exact tau-only minimum is 73,417 seeds, so every
67,338-seed cover needs at least 6,079 classes without a tau provider. The
construction begins with the exact tau-only cover, removes seeds while the
four-map cover remains complete, exchanges two selected seeds for one new
seed, then makes one-for-one swaps that increase tau coverage.

For every seed, the full offer set consists of residue classes reached by
`1`, `tau`, `tau^2`, and `rho` with digit norm at most `1024^2`. The tau offer
set excludes `rho`. Pruning chooses a removable seed with the fewest classes
that lose their last tau offer, breaking ties by seed norm and class index.
An exchange is admitted only when adding the new seed and removing both old
seeds leaves every full-cover count positive. Each accepted change records
its class indices and its exact change in tau-uncovered classes. The final
one-for-one pass uses the parent orbit-swap search to improve tau coverage
without changing the table size.

The independent exchange verifier rebuilds six-unit residue classes and
digit actions, replays every exchange, and checks the final seed sequence.
The independent cover verifier checks the priority assignment and all
1,048,576 residues for the pruned, exchanged, and refined atlases. The
single-target scalar input panel is drawn only after source and cover bytes
are frozen in a commit. It is disjoint modulo the secp256k1 group order from
the preceding panel set. Each scalar path is replayed against its original
scalar and compared with the fixed-size swapped cover; the first 128 point
fixtures are computed independently by binary multiplication.

Native replay materializes the full direct-XYZZ evaluator with the refined
atlas and checks all 4,096 scalar outputs against the independent adic path,
plus binary multiplication on the first 128 inputs. CPU wall-time comparisons
require the host isolation receipt in `docs/ISOLATED_BENCHMARKS.md`; path
counts and source-call counts are algorithmic diagnostics.
