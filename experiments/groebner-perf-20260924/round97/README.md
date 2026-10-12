# Bounded scratch reuse in normal reduction

Round97 replaces repeated fresh output vectors in ordered normal-reduction
merges with bounded, per-call scratch storage. The comparator, logical charges,
XOR witnesses, independent checker and complete-query boundary stay unchanged.
The baseline and default remain available; the candidate is explicit.

The candidate reduces requests for new vector storage on the frozen panel,
while preserving every accepted result and every work-limit failure. Local
complete-query times are mostly flat and do not establish a speedup.

- [Protocol and storage contract](PROTOCOL.md)
- [Results, limitations and next decision](RESULTS.md)
- [All 92 timing/storage cells](summary.json)
- [Baseline stack samples and next representation hypothesis](SAMPLES.md)
- [Lossless evidence archive](results.tar.gz) and [custody receipt](archive.json)

Optimized and UBSan validation passed five test groups, 6,144 direct native
merge cases per build, 184 complete-query control calls, 552 preset diagnostic
calls and 26 corruption controls. All proofs and non-timing traces match.
