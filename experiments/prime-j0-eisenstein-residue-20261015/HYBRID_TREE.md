# Affine/projective reduction screen

The norm-110557 full two-x table can feed a hybrid reduction tree. Two variants retain the same 27,429,548-byte table and run either two or three batched affine layers, then join the remaining partial sums in XYZZ coordinates and batch-normalize the final 128 outputs. Both reproduced every point in the frozen 12,288-scalar fixture.

The [hash-guarded overlay](native_alt_hybrid_overlay.py) adds both paths to the frozen alternate-radix source. The [native provenance archive](alt-hybrid-native-provenance.tar.gz), SHA-256 `18cd292b61920873fa67cac896021ca5778d33d39a3ea803ee1fe31abfb25df5`, retains the exact source, binary, fixture, build, stdout, and stderr. The [audit script](audit_alt_hybrid.py) generated the [exact-replay record](alt-hybrid-audit.json).

| Full 12,288-scalar diagnostic | Two affine levels | Three affine levels | Four affine levels (prior alternate radix) |
| --- | ---: | ---: | ---: |
| Timed interval | 62.978376 ms | 60.953218 ms | 60.181416 ms |

The hybrid diagnostics are close to the earlier all-affine value and to the observed Tier 1 noise. They establish correctness and the cost shape, not a qualified ranking. The three-level variant removes only the final affine layer and adds XYZZ pair joining plus final batch normalization; the two-level variant moves two final layers to XYZZ. Neither diagnostic points to a large reduction in group-operation cost.
