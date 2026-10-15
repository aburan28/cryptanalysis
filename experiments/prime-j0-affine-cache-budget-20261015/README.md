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

The recurrence behind the fixture is formalized in
[StreamFixture.lean](StreamFixture.lean) as `StreamFixture.hom_progression`:
for any scalar-to-point map preserving addition, adding one fixed scalar step
on every pass maps to adding its point image on every pass. Its hypotheses
are the scalar and point additions and the homomorphism law; the file does
not assert a concrete curve implementation. The pinned Lean 4.34.1 command
`lean StreamFixture.lean` passed, and `#print axioms` reported none in
[lean-check.log](lean-check.log). The generator independently checks the
concrete secp256k1 base points and step point before using that recurrence.

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

Job `1b1489f47213478b9aab096de03ce244` completed with 96 valid arms,
48 valid pairs, stable artifact hashes, and no A/A ratio outside
`[0.90, 1.11]`. The independent [audit](tier1-affine-stream-cpu40-audit.json)
re-generated the fixture, checked source and executable bytes against the
frozen hashes, re-parsed every raw stdout, matched every expected point and
fixture field, and evaluated all adjacent A/A gates. The comparison-only
median ordinary-affine/full-two-x ratio is **1.087393**, with a paired
bootstrap 95% interval **[1.074663, 1.106558]** over 16 comparison
repetitions. Mean online time per 12,288 distinct outputs is 71.422170 ms
for ordinary affine-layer and 65.473654 ms for full two-x, or 5.812351 and
5.328260 µs/output. Mean table preparation is 3966.995 and 3978.971 ms
respectively. This is a qualified Tier 1 batch-throughput result for the
specified arithmetic progression of scalars. Uniform random scalars and
single-scalar latency remain separate measurement questions.

The generic runner's `paired_speedup=1.005872` pools the comparison with
two A/A case medians. Its `speedup_claim_eligible=false` reflects that this
three-case calibration panel has no generic cross-case bootstrap. The
predeclared case-specific audit uses the A/A cases as noise gates and
computes the comparison interval separately. All raw
[run receipts](1b1489f47213478b9aab096de03ce244) are committed. Their
sealed archive had SHA-256
`2d315d9190b46e8cd0342bf92d046cdda32ec83e5b11372301ed73c5e8869187`
at both ends of the transfer. The exact source, binary, tests, generator,
fixture, and direct screen are in
[prime-j0-affine-stream-panel-provenance.tar.gz](prime-j0-affine-stream-panel-provenance.tar.gz),
SHA-256 `cf7f53a58eb03c856b4c7a04009893370a678398a0763a4ae7f73b5c24c51d46`.
