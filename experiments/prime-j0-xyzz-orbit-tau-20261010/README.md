# XYZZ accumulator for the fused orbit-tau scalar format

The XYZZ accumulator saves **73,717 field squarings** across a post-freeze 4,096-scalar panel compared with the fused orbit-tau Jacobian accumulator, while using the same 5,726,228-byte table and the same number of field multiplications. Both complete output streams match independently computed secp256k1 points, including ten scalar reduction boundaries. The source is frozen at `25e660b916c20d5c2e596f470af892d9d6a74d8b`.

This candidate keeps the nineteen-window Eisenstein recoder and fused `P`/`tau(P)` cube-root table from the parent branch. It changes the online accumulator to XYZZ coordinates, allowing each ordinary affine table-point addition to use **8 field multiplications and 2 squarings**. The parent Jacobian path uses 8 multiplications and 3 squarings. Both formats retain the same 5,726,228-byte table and accept public scalars through separate opt-in CLI modes.

An XYZZ tuple `(X,Y,ZZ,ZZZ)` represents `(X/ZZ,Y/ZZZ)` with `ZZ^3=ZZZ^2`. For a mixed addition with affine `(x2,y2)`, the implementation computes

`U2=x2*ZZ; S2=y2*ZZZ; P=U2-X; R=S2-Y; PP=P^2; PPP=P*PP; Q=X*PP;`

`X'=R^2-PPP-2Q; Y'=R*(Q-X')-Y*PPP; ZZ'=ZZ*PP; ZZZ'=ZZZ*PPP`.

These are [Sutherland's XYZZ mixed-addition formulas in the Explicit-Formulas Database](https://hyperelliptic.org/EFD/g1p/auto-shortw-xyzz.html). Equal points use its doubling formula; inverse points return the identity. The final conversion inverts `ZZZ` once, derives `1/Z = ZZ/ZZZ`, and computes the affine coordinates. This preserves the exact scalar identity established for the fused orbit-tau table.

The 110-test release suite compares 128 chained XYZZ and Jacobian additions, checks `ZZ^3=ZZZ^2` after each, covers equal and inverse inputs, and compares the complete 4,096-scalar prior panel with the parent mode and independent binary multiplication for its first 128 cases. After source freeze, `make_inputs.py` draws a disjoint 4,096-scalar panel, `make_fresh_fixture.py` computes independent binary points, and `run_fresh.py` replays both formats. `make_edge_fixture.py` and `run_edges.py` cover ten reduction boundaries. `verify_fresh.py` binds the source, inputs, fixture, edge cases, and complete output streams.

## Exact point-kernel diagnostic

Both modes use the same post-freeze panel and one source-instrumented binary. The fused table is warmed before wrapper counters are reset for each scalar and mode.

| Accumulator | Field adds | Field subs | Field muls | Field squares | Retained table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jacobian | 73,717 | 481,357 | 589,736 | 221,151 | 5,726,228 |
| XYZZ | 73,717 | 481,357 | 589,736 | **147,434** | 5,726,228 |

The counter boundary is the `u256_add`, `u256_sub`, `u256_mul`, and `u256_square` wrappers during point evaluation. It includes mixed additions and any exceptional branches taken on this panel, and excludes table construction, scalar recoding outside those wrappers, final inversion, output conversion, and hardware time. The [counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind the count to frozen source. The [release log](release-tests.log) records 110 passed tests. A controlled wall-time comparison requires the repository's host isolation preflight.

From a full checkout, verify the committed receipts with:

```sh
python3 experiments/prime-j0-xyzz-orbit-tau-20261010/verify_fresh.py
python3 experiments/prime-j0-xyzz-orbit-tau-20261010/verify_ops.py
```
