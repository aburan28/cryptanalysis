# Radius-two matching atlas for fixed-generator tau comb: frozen protocol

## Candidate

The existing adaptive path stores pair sums for all eleven adjacent edges
among twelve ordinary tau-comb rows. Add the ten distance-two edges,
giving `G2 = {(i,j): 0 <= i < j < 12, j-i <= 2}` and 21 pair tables.
Each edge retains `81 * 81 * 6 = 39,366` compact affine points, so the
slot budget at 104 bytes per point is 85,975,344 bytes, below 90 MiB.
The sparse top row and its terminal repair stay unchanged.

For every 12-bit active-row mask, construct a deterministic maximum
matching on the induced graph, before processing any scalar. Use the
recurrence `F(M)=max(F(M\\{v}), 1+F(M\\{v,w}))` over neighbors `w` of
the least active row `v`; break equal-cardinality ties by choosing the
lexicographically smallest sorted edge sequence. Store the 4,096
decisions in a small atlas. During scalar evaluation, form the active
mask for each of 13 columns, add the precomputed point for every matched
edge, then add unmatched row digits. This is a variable-time method for
public scalars. The online timer must include matching lookup, point
lookup and decoding, all nine scalar-dependent recodings, group work,
affine output, and correctness assertion. Table preparation is separate.

## Frozen screen and gates

Draw 4,096 uniform scalars from `[0,n)` with
`random.Random(20261009241)` for a design panel and 4,096 with
`random.Random(20261009242)` for disjoint holdout. Use the exact native
nine-choice path binary at commit `b47435b9` to get selected
representatives; reconstruct its width-six digit streams independently.
For every case, verify the reconstructed radius-one matching count
equals the native `pair_fusions` field. Compute exact maximum matchings
for `G1` (eleven distance-one edges), `G2` (21 distance-one-or-two
edges), `G3` (30 edges with distance at most three), and the complete
66-edge graph as an operation-count bound. Record additions, tau maps,
point-operation proxy `5*tau_steps + 11*mixed_additions`, mask
distribution, per-scalar fusion deltas, and retained table bytes. `G3`
and the complete graph are comparison points, not implementation
decisions in this protocol.

Implement `G2` only if holdout proxy falls at least 3% versus `G1`,
every case has at least as many fusions as `G1`, and the 90 MiB slot
cap holds. For the native candidate, require exact affine points,
selected representatives, tau counts, terminal repairs, and predicted
fusion counts versus the baseline on five boundary inputs, 214 frozen
inputs, all 129 expected-point fixtures, and both fresh panels.
Independently replay at least 256 fresh points and every fixture.
Run the release tests, including sampled direct pair-sum checks for
all ten new distance-two edges. Generate a 129-case, seven-repeat
paired isolated-host manifest. CPU wall-time claims require the host
isolation and noise gates in `docs/ISOLATED_BENCHMARKS.md`; operation
counts alone remain a stage result.
