# Exact F4 basis caching completed two paired screens

The opt-in bounded-bitset eligibility counter and cached stable reducer order
preserved the exact reduced basis, assignment, proof bytes, producer work, and
independent checker work on all five frozen 12-variable point-decomposition
queries. Each candidate passed 10 optimized/UBSan complete-query controls and
seven 13- to 64-variable width controls, including rejection of deliberately
corrupted proof outputs. The second candidate reduced local native F4 time in
most paired cells; complete-query timing was too variable on this contended
host to promote a controlled CPU speedup.

| Query | Eligibility count: complete query | Eligibility count: native F4 | Count + priority: complete query | Count + priority: native F4 |
| --- | ---: | ---: | ---: | ---: |
| `pdp-12-seed-1` | 0.959 | 0.934 | 0.587 | 0.652 |
| `pdp-12-seed-2` | 1.043 | 0.967 | 0.963 | 0.897 |
| `pdp-12-seed-3` | 1.062 | 1.026 | 0.991 | 0.882 |
| `pdp-12-seed-4` | 0.979 | 0.962 | 1.037 | 0.351 |
| `pdp-12-seed-5` | 0.815 | 0.953 | 0.825 | 0.885 |

Entries are medians of five paired candidate/reference ratios, with smaller
values faster. The geometric means of those five cell medians were 0.968 for
the eligibility-count native F4 and 0.968 for its complete query; for the
priority candidate they were 0.694 and 0.863 respectively. The priority
candidate's pooled median over all 25 paired complete-query ratios was 0.974.
Its individual complete-query ratios spanned 0.313 to 3.335 for seed 1 and
0.729 to 2.287 for seed 4. All 100 measured query executions completed and
matched the reference's exact proof and work; 20 additional queries were
warmups. No failed or timed-out row was omitted.

The frozen input is the round112 independently audited `GF(2^31)` panel with
modulus `2147483657`, binary curve coefficient `b=1`, three summands, and four
factor-base coordinates per summand. The reference is the round119 bounded
bitset engine. Each complete-query interval starts at fresh target coefficient
descent and ends after independent proof, original-equation, and curve checks
and lease teardown. The native F4 interval is the engine's exclusive phase
timer. Fixture construction and reusable setup are outside both intervals.
The first source snapshot is `4884965ad6e9240170bfffa5b78bb7f319d65ee6`;
the priority snapshot is `ad6b75b26bca5f622f55c7a40a763df35bbf777d`.
Both were committed before their respective builds and measurements.

The first profile ran while the local Apple M4 Pro load average was roughly
102–149; after the second, it was roughly 68–130. These are exploratory
timings. The accessible Linux benchmark allocation reports a Docker cgroup v1
hierarchy, no isolated cgroup v2 CPU partition, and no `nohz_full` CPUs; it
does not meet the [isolated CPU benchmark contract](../../../docs/ISOLATED_BENCHMARKS.md).
The separate GPU host was unreachable when rechecked. A matched physical-host
receipt is still needed to decide whether either cache improves complete-query
wall time under controlled conditions. Until then, both remain opt-in
experimental engines.

The byte-verified [evidence archive](results.tar.gz) contains 462 logical
files and has SHA-256
`ead9752fb5c9afe8fb1a1b5cced5115f01c415fe31cbf3d2b92e5d22d538fa00`.
It includes every panel and profile row, original result and proof artifacts,
build receipts, both generated engines, exact source snapshots, and the
independent reference panel. [archive.json](archive.json) records its count,
size, hash, and verification status. The
[CI workflow](../../../.github/workflows/groebner-bitset-fitcache.yml) builds
the pinned reference, reruns exact controls on Ubuntu and macOS, and retains
all worker artifacts; its three-pair profile is a correctness and portability
check rather than an isolated-host performance claim.

The next optimization should target the measured complete-query cost outside
native F4, especially independent proof checking, or improve the bitset kernel
enough to change the complete-query interval under a qualified host. A GPU
comparison must include packing, transfer, launch, synchronization, and final
verification for one query.
