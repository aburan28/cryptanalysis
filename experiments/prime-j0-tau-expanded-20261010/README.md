# Tau-preexpanded nineteen-window scalar format

The 19-window table stores both `P` and `tau(P)` as affine points for each seed. Each digit selects its precomputed tau exponent; all selected points accumulate in one Jacobian bucket. This removes the online degree-three tau map and final projective addition. Grouped unit powers need at most two bucket rotations.

The format retains 2,916,756 bytes across 21,949 table slots, the same byte count as the orbit-X format. Compared with the original 19-window format, this buys a different operation path for 1,404,736 additional retained bytes. The evaluator is a public-scalar research path with scalar-dependent table indices.

`native-tau-expanded-delta.patch` applies after the 17-window, 19-window, and orbit-X patches in the scalar PR. The source receipt binds the scratch implementation before the fresh panel draw. The native tests check all 21,930 nonidentity `tau(P)` table points against the separate native tau map, 4,096 prior scalar outputs with 128 independent binary point checks, and the complete 106-test release suite. CPU timing requires the isolated benchmark preflight.

The [fresh replay](FRESH_RESULTS.md) records 4,096 disjoint post-freeze scalars, independent point expectations, three native output streams, and source and result verifiers.
