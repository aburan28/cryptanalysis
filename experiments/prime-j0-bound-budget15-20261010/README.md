# Fifteen-window weighted digit-budget candidate

Mode 156 combines a 15-window `8^6,9^9` bit schedule, a full `D=512`
radix-512 two-bucket `tau` atlas for the first eight nine-bit windows, and
the tight `D=363` atlas at the final window. It retains **233,423** affine
seed points and **17,511,596 bytes** including atlases, container overhead,
and the Solinas unit constants. The exact termination proof and atlas
construction are in [`PROOF.md`](PROOF.md) and `build_atlas.py`.

The first native replay matched the preceding mode 155 on 4,096 scalars
from the earlier compact-affine panel and independently matched binary
scalar multiplication on its first 128 points. It counted **57,344**
nonidentity mixed additions for mode 156 and **61,439** for mode 155 on
those same scalars, a reduction of 4,095 additions. This is a source-level
operation count with an explicit 9,174,972-byte increase in retained data.

The next gate is a disjoint source-frozen panel with independent point
fixtures and a complete release-suite replay. CPU wall-time ratios require
the host-level isolation receipt in
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
