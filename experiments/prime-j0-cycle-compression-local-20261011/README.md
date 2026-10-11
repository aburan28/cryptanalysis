# Local native replay of the compressed scalar cover

The 6,094-class radix-1024 cover passed a release-mode native replay on
ARM64. The frozen 4,096-scalar panel matched the independently certified
adic digits and point results; the first 128 points also matched independent
binary multiplication. The replay reported 1,403 rho-active paths, 1,696
rho digits, 49,152 additions, 19,393 gauge products, and 54,339,936 retained
bytes.

The [source-bound receipt](local-targeted-check.json) records the raw test
log, compiled binary hash, generated-source and asset hashes, materialization
chain, test filter, and toolchain. The candidate cover and fresh panel are in
[the construction record](../prime-j0-cycle-compression-20261011/RESULT.md).
The [native atlas and Linux workflow](../prime-j0-cycle-compression-native-20261011/RESULT.md)
remain the cross-platform replay path.

This is a correctness run. CPU wall-time comparisons require the host-level
isolation receipt specified in `docs/ISOLATED_BENCHMARKS.md`.
