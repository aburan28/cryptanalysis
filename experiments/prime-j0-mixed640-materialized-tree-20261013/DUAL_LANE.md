# Dual-lane streaming reduction for the pre-tau mixed-radix evaluator

The dual-lane evaluator accumulates the fourteen selected affine points in
two alternating streams and joins the two XYZZ results once. It retains the
same selective 64 MiB table, mixed-radix recoder, point-selection code, and
affine recovery as the vector-tree evaluator. Two live lane states replace
the selected-point vector and per-level reduction vectors. Source generation
is in `native_dual_lane.py`.

Each lane starts empty, retains its first selected point in affine form,
joins its second point with the affine-pair formula, and adds later points
with the mixed XYZZ-affine formula. Zero seed choices are skipped before
assigning the next lane, so the streams differ in length by at most one.
For fourteen nonidentity choices, each lane makes one affine-pair join and
five mixed joins; the final XYZZ join gives the same **126 generic
field-kernel calls** as the balanced tree under the existing 6/10/14-call
formula model. The scheduling change targets allocation, copying, and
instruction overlap, while retaining the operation count.

## Algebra and proof map

For a list of selected curve points, `split` sends successive points to
alternating lanes. The lane result is the left-associated sum of each lane;
commutativity and associativity make their final sum equal the original
selected-point sum. `DualLane.lean` proves this for arbitrary list length,
including empty and singleton lanes:

| Result | Lean declaration | Exact assumptions | Status |
| --- | --- | --- | --- |
| Alternating lanes reconstruct the selected list | `PrimeJ0DualLane.weave_split` | List construction only | Checked |
| Interleaving preserves the sum | `PrimeJ0DualLane.sum_weave` | Associativity, commutativity, left/right identity | Checked |
| Left-associated runtime lanes preserve the full sum | `PrimeJ0DualLane.dual_lane_foldl` | Associativity, commutativity, left/right identity | Checked |

The module builds with pinned Lean 4.34.1. All seven `#print axioms`
audits list only Lean's standard `propext`; the command, output, version,
and source hash are in `dual-lane-lean-receipt.json`. The abstract group
laws apply to elliptic-curve point addition. Connecting the Lean point
operation to this Rust XYZZ implementation remains a separate bridge;
the native check below covers the executed formulas on the frozen inputs.

## Native and paired result

The Linux release build passed
`source_frozen_holdout_matches_independent_binary` on all 128 scalars in
`selective-holdout.json`, comparing each result with an independent affine
fixture and binary scalar multiplication. The selected table retained
67,010,468 bytes. The Tier 1 service compared the existing selective
vector tree with the dual-lane evaluator on holdout case 0, using eight
alternating-order pairs on CPU 14, NUMA node 0:

| Panel | Valid pairs | Median vector/dual online ratio | Paired bootstrap 95% interval | Median preparation, vector/dual |
| --- | ---: | ---: | ---: | ---: |
| Selective vector versus dual lane | 8/8 | 0.9986 | 0.9860–1.0583 | 10,552/10,516 ms |

All sixteen invocations verified the same frozen point and had stable
artifact, binary, and runner hashes. The online interval included recoding,
lookup, selection, group evaluation, and affine recovery; table preparation
was recorded separately. Individual pair ratios include a 1.366 outlier,
so the median and paired interval are more informative than the maximum.
The interval includes 1 and the Pod has instance-scoped Tier 1 isolation
without host-exclusive CPU evidence. This case leaves the latency effect
unresolved; a multi-case paired panel is the next timing gate.

The complete raw result is
`tier1-runpod-20261013/f80885f17f99468d969d5b93e10f45d3/`.
The transferred archive's SHA-256 was
`dc3a73f134c3421710804208b1c9b461a4a28981561f57aae59b295f9b1f8a0c`.
The dual-lane release binary SHA-256 was
`1bb0bd3a3de7c9a0832207fe09d04ceb6010363df4e991f71d4d3f846ac8cc6a`.
