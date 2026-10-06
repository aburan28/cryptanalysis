# Next GPU experiment: compact exact symmetry representatives

The current Metal kernel launches one SIMD group for every fixed-block
assignment, even after the host has proved exact exchange symmetry and will
consume only canonical representatives. The supported shader can avoid this
redundant work within one query. This is separate from widening the kernel or
moving affine-certificate generation onto the GPU.

For even fixed dimension `x=2h`, let `n=2^h`. The canonical branches satisfy
`branch <= swap(branch)`; there are `n*(n+1)/2`, including every diagonal once.
Build an immutable map from compact indices to these exact branch IDs during
target-independent workspace setup. The map depends only on the validated
dimension. Do not cache specialized coefficients, numerical pivots or answers.

After each query's fresh coefficient-wise symmetry test, pass an explicit
dispatch mode and branch count to the GPU. When symmetry is proved, launch
only the compact count and read the map uniformly within each SIMD group.
Write reduced rows and full equation-combination witnesses at the original
branch offset so the host can preserve its existing certificate expansion.
When the test fails or `x` is odd, use the full identity mapping and full grid.
Never read stale alias output; test symmetric/asymmetric/symmetric reuse of
the same context. Out-of-range compact groups must return uniformly before
any shuffle or collective.

Keep full input/output buffers initially so this experiment isolates scheduling.
Record map storage, actual groups/branches dispatched, transfer bytes, host and
device time, and CPU expansion/checking costs. Include the map's allocated
bytes exactly once in workspace accounting. Evaluate compact packing as a
later ablation only if transfer is the measured bottleneck. An arithmetic
inverse of triangular indices is a separate hypothesis; a validated lookup
map avoids floating-point boundary corrections in the first implementation.

Required controls include all diagonals and off-diagonals, both input mask
widths, cancelled duplicate ANF terms, false symmetry, odd fixed dimension,
zero/inconsistent/rank-deficient systems, wide equations that require CPU
fallback, corruption, and workspace reuse. CPU and GPU must emit complete
mathematically equivalent certificates checked from the original ANF. Compare
the compact kernel against the unchanged full-grid kernel and the strongest
paired CPU on complete single-query timing. Charge launch, synchronization,
copy/hash, expansion, independent equations/basis checks and curve replay.

The supported kernel remains limited to at most 31 lifted features and 32
equations. After measuring compact scheduling, treat wider constant elimination
and bounded GPU affine provenance as distinct experiments. CPU fallback stays
available; Metal evidence does not establish CUDA, OpenCL or physical x86 GPU
compatibility. Neither scheduling nor fixed CPU loops changes general Gröbner
basis asymptotics.
