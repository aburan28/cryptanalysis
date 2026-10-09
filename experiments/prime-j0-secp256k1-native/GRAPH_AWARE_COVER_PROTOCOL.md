# Graph-aware representative selection: frozen screen

## Candidate and accounting

Keep the exact 33-edge balanced pair tables, 13-column comb, width-six
digits, and nine hexagonal Eisenstein lattice representatives from the
parent. For each valid representative, compute its 13 active-row masks and
look up the cardinality of the exact maximum matching for each mask. Select
the representative minimizing

`5 * tau_steps + 11 * (unfused_mixed_additions - matched_edges)`.

The unfused count includes the sparse top-row repair and excludes the
first point contribution. Ties use the existing norm-ranked representative
order. This rule can be implemented with the current 4,096-entry atlas and
the current 93,533,616 retained pair-table bytes; it adds mask scoring
to each of the nine recodings. The current graph33 selector instead
minimizes the same proxy before matching. This is a public-scalar method.

## Frozen inputs and decision

Draw independent design and holdout panels of 2,048 scalars each, uniformly
from `[0,n)`, using `random.Random(20261009411)` and
`random.Random(20261009412)`. Use the fixed graph33 release executable
with SHA-256
`a7a43630b2435daee293d9888b76527d345c56dec21bac500a8e91f5712b35e8`
as the baseline. Score all nine representatives independently in Python,
including failed 162-digit recodings, the sparse top repair, all matching
masks, and the rank tie rule. Check the first 128 cases of each panel
against the native baseline's representative, tau count, repair status,
fusion count, and mixed-addition count. Preserve per-case ranks and cost
deltas, aggregate operation counts, input and artifact hashes, and any
failures. The design panel is an implementation diagnostic; only the
untouched holdout decides the gate.

Implement the joint selector in native code if holdout point-operation
proxy decreases by at least 1% versus graph33 and no scalar has a larger
proxy. The native correctness gate must compare exact outputs on the
129 fixture points, five boundary scalars, 214 previously frozen scalars,
both new panels, and at least 256 independently computed points. Keep the
old graph33 mode for a paired comparison. If the proxy gate does not pass,
record the result and stop this candidate.

The proxy counts five field products per ordinary tau step and eleven per
ordinary mixed addition. It omits representative scoring, table lookup,
cache misses, and exceptional point paths. An online CPU improvement needs
a full-operation paired receipt from a host passing
`docs/ISOLATED_BENCHMARKS.md`; these screen counts cannot establish one.
