# Linked atlas for shared-Z mixed-radix scalar multiplication

The degree-seven shared-Z path previously used the original nine digit
orbits. This screen substitutes the linked nine-orbit atlas and constructs
its seeds with the simultaneous conjugate degree-seven formulas already
implemented in `src/main.rs`. Its exact norm-4096 tail uses the same
2/τ/ρ/conjugate-ρ transition rules and cost model, but the linked width-four
digit representatives. The linked seed preparation charges 68 M+S per
one-use base rather than 83; common-Z alignment still charges 57.

`generate_linked_shared_z_tail.py` produces
`linked-shared-z-tail4096.bin` (5,329 bytes, SHA-256
`56c1e92b44ed14ce5b807c33159bf1f46850f1ce8eb0aff8582c961ce5fc8fd7`).
The generator audits 29,688 states and 138,240 transitions, then
reconstructs every path. Native tests reconstruct both the original and
linked tables for all 59,376 state/table combinations, including the
pending-τ bit. All 44 release-mode Rust tests passed.

## Paired source-operation screen

Both arms ran through the same release executable, recomputed the scalar
representative and digit stream, and checked every output against the frozen
affine point. Counts include one-use seed preparation, common-Z alignment,
and charged scalar steps and additions in the repository's established
source model. That model omits the one final common-Z restoration
multiplication in both arms. Counts also exclude integer recoding cost,
memory traffic, affine conversion, and output checking; they are not CPU
timings. The omitted restoration has no effect on the paired reduction.
All panels were existing fixtures, reused here for validation.

| Frozen panel | Cases | Original exact tail M+S | Linked exact tail M+S | Reduction | Linked wins / ties / losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Design | 64 | 83,240 | 82,772 | 468 | 43 / 0 / 21 |
| Fresh | 256 | 333,095 | 330,994 | 2,101 | 168 / 4 / 84 |
| Coset | 256 | 332,943 | 331,038 | 1,905 | 164 / 5 / 87 |
| Linked fresh | 256 | 332,749 | 330,962 | 1,787 | 164 / 10 / 82 |
| Zero-τ | 256 | 332,844 | 331,564 | 1,280 | 151 / 8 / 97 |

The no-tail linked candidate also passed all 1,088 scalar cases; on the
fresh panel it counted 334,296 M+S, below the original no-tail path's
335,685 but above the original exact-tail path's 333,095. The linked
exact tail is needed for the full reduction. The fresh-panel reduction is
2,101/333,095 = 0.631% in this source model. The variant remains
variable-time research code.

The fixture SHA-256 digests, in table order, are
`2e8da438343ecf650c9d8d9b2a593f5d603027c4c1f81485f2456c38028491d4`,
`73d0e94aa439d48dbba79fb9b88b460fbca7c0982e814c66c6387e5dfa9a6bce`,
`2d90d33ab939db8f57a831328efb194cf83ed21d6558db7e87a086312bb1177b`,
`188baa1cfe4ab49afe148ae6a28961833eb31efd5cfa2de9ced2dcc38191bef1`,
and `9018f9a560648080d069ec9eed34a9b066808bb327a354db5cecd19534229243`.

## Controlled timing handoff

`make_shared_z_degree_seven_manifest.py --linked-atlas` pairs the original
and linked exact-tail modes on the same one-use scalar cases. Each native
`online_ms` interval starts before parsing the scalar and base and includes
integer lattice reduction, recoding, seed preparation, common-Z alignment,
evaluation, affine conversion, and the frozen-point check. The manifest
excludes process launch, fixture loading, and lazy constant initialization
from both arms. It names both generators and tail tables as artifacts.

The 256-case linked manifest passed `isolated_bench.require_manifest` with
synthetic topology fields. Both benchmark CLI modes emitted `verified=1`,
an `online_ms` field, and the same frozen output for one paired smoke case.
This was a structural and correctness check, not a host-isolation preflight.

No qualifying host-isolation receipt exists for this comparison. The CPU
speedup and academic novelty of the combined scheme remain unknown. The
isolated service must certify host topology and noise gates before any CPU
speedup claim. The previously examined RunPod Pod failed the host gate.
