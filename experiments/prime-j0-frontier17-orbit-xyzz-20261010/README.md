# Seventeen-window orbit-tau XYZZ scalar format

The seventeen-window format saves **65,496 field multiplications and 16,374 field squarings** across a post-freeze 4,096-scalar panel compared with the nineteen-window XYZZ format. Both complete output streams match independently computed secp256k1 points, including ten reduction boundaries. The larger table retains **11,203,808 additional bytes**. Source was frozen at `737c0615a051cef49569d44bb8e1f96e08ad9248` before the panel draw.

This candidate combines the exact seventeen-window Eisenstein recoder with a fused orbit-tau affine table and one XYZZ accumulator. It retains **16,930,036 bytes** across 64,463 table slots. The nineteen-window XYZZ reference retains 5,726,228 bytes across 21,949 slots. The shorter recoder can require at most sixteen ordinary mixed additions after its first nonidentity term; the reference can require eighteen.

For each window seed `d_j`, the table stores `P_j=[2^h_j d_j]G`, `tau(P_j)`, and three cube-root x images for each, with sign handled by negating y at selection. The exact recoder gives `a+b tau=sum_j 2^h_j u_j tau^e_j d_j`, so direct selection and accumulation returns `[a+b lambda_tau]G=[k]G`. The [XYZZ mixed-addition formula](https://hyperelliptic.org/EFD/g1p/auto-shortw-xyzz.html) is shared with the nineteen-window mode; this comparison changes the window schedule and retained table size while preserving the point coordinate backend.

The opt-in mode is for public scalars because table addresses depend on digits. The 64,446 nonzero slots produce 773,352 `(window, seed, tau exponent, unit)` images; the 112-test release suite checks them against the independent plain-point table and the separate projective tau map. Another test pairs 4,096 prior scalars with the nineteen-window XYZZ mode and independently checks the first 128 points by binary multiplication. After source freeze, the scripts in this directory drew a disjoint 4,096-scalar panel, computed independent binary points, and replayed both modes along with ten scalar reduction boundaries. `verify_fresh.py` binds the source, inputs, fixture, edge cases, and complete output streams.

## Exact point-kernel diagnostic

Both modes use the same post-freeze panel and one source-instrumented binary. Both tables are warmed before wrapper counters are reset for each scalar and mode.

| Format | Field adds | Field subs | Field muls | Field squares | Retained table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nineteen-window XYZZ | 73,719 | 480,918 | 589,752 | 147,438 | 5,726,228 |
| Seventeen-window XYZZ | 65,532 | 427,975 | **524,256** | **131,064** | 16,930,036 |

The counter boundary is the `u256_add`, `u256_sub`, `u256_mul`, and `u256_square` wrappers during point evaluation. It includes mixed additions and exceptional branches taken on this panel, and excludes table construction, scalar recoding outside those wrappers, final inversion, output conversion, and hardware time. The [counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind this diagnostic to frozen source. The [release log](release-tests.log) records 112 passed tests. A controlled wall-time comparison requires the repository's host isolation preflight.

From a full checkout, verify the committed receipts with:

```sh
python3 experiments/prime-j0-frontier17-orbit-xyzz-20261010/verify_fresh.py
python3 experiments/prime-j0-frontier17-orbit-xyzz-20261010/verify_ops.py
```
