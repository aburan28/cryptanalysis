# Affine rotation tables under a distinct-input stream

The full two-x table stores `(x, x+βx, y)` for every radix-14 digit row and
the terminal row. The cache-budget variant stores that representation in the
seven even-numbered digit rows and ordinary affine `(x,y)` in the remaining
rows. Its retained size is 31,133,444 bytes, below the pod's exposed 32 MiB
L3 slice for CPU 40, versus 37,192,948 bytes for the full two-x table and
26,035,988 bytes for the ordinary affine-layer table. The mask is fixed by
window parity, independent of benchmark inputs.

[native_cache_budget_overlay.py](native_cache_budget_overlay.py) is guarded by
the exact two-x source hashes. The resulting Linux source hashes are
`b825b50c2dabf897fafb217c8d73d774b8934ff460665e921f2fd6284b504196`
for the front and
`71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d`
for the windows. The output-verified exploratory A/B/A screen on the
repeated 128-scalar fixture measured full two-x 53.423983 ms, cache-budget
55.720036 ms, full two-x 53.779794 ms. The exact source, build, passing
independent replay, failed first Cargo launch, and screen logs are in
[prime-j0-affine-cache-budget-screen.tar.gz](prime-j0-affine-cache-budget-screen.tar.gz),
SHA-256 `0abf25572fd8f7f52ad862fddc9663513cbf4cebdd825bc8406381ddcf19c4c6`.

The original throughput panel repeated the same 128 scalars 96 times. The
new [fixture generator](generate_stream_fixture.py) independently checks the
128 base scalars against secp256k1's curve equation and binary multiplication,
derives a nonzero step from the base fixture hash, then writes 96 batches of
128 distinct scalars and points. Each point is the base point plus `j` times
the independently computed step point. The [frozen fixture](mixed640_stream_fixture.json)
contains 12,288 unique scalars and all expected points; SHA-256
`6b7ce3b515d0980b9975398b8b31e5e1cfdc9e54510d04faf29fee3f3bacf778`.
The benchmark loads the fixture and warms one table before timing, then checks
every output after the interval.

The hash-guarded [stream overlay](native_stream_overlay.py) and
[ordinary-affine arm](native_affine_stream_overlay.py) produced final front
source SHA-256 `76417bc6ae1d9eb2f219ffc89b758163cf165cc76793a4fdb654f117f9da1315`.
The final Linux binary is
`07f890c8229a547627bcb99aee4b54399068d980f96b8c31e678ed982c2082de`.
Native tests on that source passed independent binary replay for both the
ordinary affine-layer and full two-x paths. Direct output-verified screens
measured full two-x 60.634333 ms, cache-budget 64.548292 ms, full two-x
59.775939 ms; and ordinary affine-layer 68.652193 ms, full two-x 59.835450
ms, ordinary affine-layer 69.601658 ms. These screens select the full two-x
versus ordinary-affine pair for the frozen Tier 1 panel. The screen values
are exploratory.

The [Tier 1 manifest](tier1-affine-stream-cpu40-manifest.json) and
[predeclared rules](tier1-affine-stream-cpu40-rules.json) specify 16 alternating
repetitions on CPU 40 with adjacent A/A calibrations, same binary and fixture,
and all artifact hashes. The container cannot establish physical-host
exclusivity; the runner records exposed topology, cgroup, affinity, frequency,
throttling, steal time, IRQ and memory observations. All raw pairs and noisy
outcomes remain evidence. The online interval measures fresh-input
128-output batch throughput; table construction and point verification are
reported separately.
