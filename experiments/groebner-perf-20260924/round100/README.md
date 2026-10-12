# Complete-query work-budget frontier

Round100 tests whether the sorting improvements survive complete certification
and replay. It compares the original sorter, packed keys and bounded radix on
13 frozen inputs at 20/80/320 million producer work units, with the same
completion-first, last-use-release checker in every arm.

The larger budget completes nine-variable seed 4 in all arms. Its full query
cost is roughly 80–84 ms locally, with no consistent radix improvement. Most
harder fixtures remain inconclusive. Keep sorting candidates opt-in and test
reusable symbolic/Macaulay work next; do not promote time-to-failure gains.

- [Frozen protocol and complete timing boundary](PROTOCOL.md)
- [Completed results, negative findings and next decision](RESULTS.md)
- [All 117 observation cells](summary.json)
- [Lossless evidence archive](results.tar.gz) and [custody receipt](archive.json)

Validation passes seven test groups, 234 optimized/UBSan control calls,
468 preset diagnostic calls and 33 artifact-corruption controls. Proofs,
independent equations/curve replay and reconstructed liveness are checked
without loading archived native libraries. Qualified speedups remain null.
