# Positional τ table for repeated public scalar multiplication

## Frozen question and algorithm

The 25-representative selector in PR #252 reduces modeled curve operations,
but it performs 25 scalar recodings. This separate candidate changes the
**point format** for a fixed public base point used many times. It keeps the
baseline minimum-L1 Eisenstein representative and width-4 τ digit stream,
then moves all position-dependent tripling into reusable precomputation.
Fixed-base combs and τ recoding are prior art; this experiment makes no
academic novelty claim.

Start with the existing nine affine seed points `S_j` and nine `τS_j` from
`ca_ec_tau4_prepare`. For each pair index `q=0,...,63`, store affine
`T[q][0][j] = 3^q S_j` and `T[q][1][j] = 3^q τS_j`. Form the next layer by
the same j=0 Jacobian tripling formula used in the prepared evaluator, then
batch-normalize each 18-point layer. A nonzero width-4 digit at τ position
`i=2q+parity` selects `T[q][parity][seed]`. Apply the existing unit rotation
`(power+q) mod 3` and sign `digit.sign × (−1)^q`, then mixed-add it to the
accumulator. No tripling occurs in the online scalar evaluation. Reject a
scalar requiring `q>=64` rather than silently truncating its chain.

The table has exactly `64 × 2 × 9 = 1,152` `ca_elem` entries, currently
36,864 bytes, plus the original prepared table. Measure and report all
table construction, normalization, memory, and scalar recoding costs. The
primary workload is repeated scalars on one prepared base: preparation is
recorded separately, and the online interval begins before the first
scalar recoding and ends after the last affine result is produced. Cold
single-call accounting includes the table build and is supplementary.

## Frozen held-out panel and decision

After this protocol is committed and its stacked PR is opened, generate four
new 4,096-scalar lists. Use the exact two curves and points in
[INTEGRATION.md](INTEGRATION.md), with SplitMix64 and little-endian unsigned
64-bit storage as specified there, replacing the initial seed by
`20261005`. Use one state per curve/point with
`20261005 XOR (curve_index << 32) XOR point_index`; preserve every reduced
scalar and its order. Commit the files, SHA-256 hashes, and an independent
generic-multiplication output digest before any isolated timing.

For each case, compare the baseline prepared τ path and this positional path
on the identical point and scalar list. Independently replay every output
with `ca_group_mul`, preserve raw errors, and record online additions,
rotations, triplings, precompute triples, table memory, and preparation time.
Use the isolated benchmark service with at least five AB/BA paired
repetitions and the same host-level noise gates as PR #252 before making a
wall-time claim. A complete verified panel and zero online triplings are
necessary correctness gates. Promote this format for repeated-base work only
if the isolated paired online wall result beats baseline; report cold cost
and the break-even target count separately. The algorithm is variable-time
and intended for public rho or research scalars.

## Frozen-panel correctness and operation result

This protocol was committed as `9adf426a` and opened as PR #254 before the
new scalar files were generated. [make_pos_inputs.py](make_pos_inputs.py)
created the four files in [pos-inputs/](pos-inputs/) using seed `20261005`;
[pos-inputs.json](pos-inputs.json) records every file SHA-256, exact public
point, input digest, and independent generic-multiplication output digest.
The [C benchmark](bench.c) now has an explicit `pos` arm.
[check_pos_panel.py](check_pos_panel.py) retained all stdout, stderr,
return codes, source hashes, and operation counts in
[pos-panel.json](pos-panel.json). Both arms independently replayed all
32,768 scalar outputs against `ca_group_mul`; all four frozen cases verified.
The positional arm executed **zero online triplings** in every case.

| Curve and point | Baseline online weight | Positional online weight | Modeled online reduction |
| --- | ---: | ---: | ---: |
| `glv-j0-32`, generator | 516,218 | 259,828 | 49.67% |
| `glv-j0-32`, `37P` | 518,207 | 260,937 | 49.65% |
| 56-bit subgroup, generator | 1,211,747 | 556,327 | 54.09% |
| 56-bit subgroup, `37P` | 1,213,102 | 557,212 | 54.07% |

Each positional table used 37,968 bytes including the original prepared
table and charged 1,134 precompute triplings plus 63 layer-normalization
inversions for these inputs. Those costs
are outside the prepared online model above and must be included in a cold
or break-even analysis. This is an exact operation-count diagnostic; the
ordinary-host wall values in raw stdout are exploratory and support no CPU
speedup claim. The modified C curve test passed 9,301 checks, including
1,012 direct point comparisons of baseline, cost-aware, and positional outputs.
The full local suite again passed 14/15; `coord` failed at localhost `bind()`
under this sandbox. Raw output is [pos-ctest.log](pos-ctest.log), with the
passing [curve log](pos-test-curve.log). The exact compiler, source, input,
and command receipt is [pos-check.json](pos-check.json).

[make_isolated_manifest.py](make_isolated_manifest.py) accepts
`--fixture pos-inputs.json --input-dir pos-inputs --candidate-arm pos` to
generate the host-bound comparison. Its output passes the merged runner's
manifest schema; host isolation and wall-time results remain pending.
