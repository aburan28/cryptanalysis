# Orbit-X cached nineteen-window scalar format

The 19-window cycle-cover table stores all three cube-root X coordinates and one Y coordinate per nonidentity seed. A selected unit contributes directly to one of two tau buckets, removing runtime bucket rotations. Sign remains a Y negation.

The native scratch prototype uses format 139 and retains 2,916,756 bytes, compared with 1,512,020 bytes for format 138 and 4,553,140 bytes for format 137. It uses the same 19 windows and 21,949 table slots as format 138. The attached patch applies after the format-137 and format-138 patches. This is a public-scalar path with scalar-dependent table indices.

The source receipt binds the exact scratch source before the new full-range scalar panel is drawn. Native tests check all 131,580 unit images against the independently checked format-138 point table and replay 4,096 prior scalars, including 128 independent binary scalar multiplications. CPU timing requires a qualifying isolation receipt.

The [fresh replay](FRESH_RESULTS.md) adds 4,096 disjoint post-freeze scalars, independent point expectations, native output streams for both formats, and verifiers for the source and result receipts.
