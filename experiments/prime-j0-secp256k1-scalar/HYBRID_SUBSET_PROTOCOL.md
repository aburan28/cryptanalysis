# Fixed-subset width-three/width-four τ recoding experiment

This experiment asks whether a **fixed small coefficient alphabet**
can retain most of width-four sparsity while reducing single-use
base-point preparation. It uses existing width-three and width-four
τ residue tables. At a nondivisible ring state `(a,b)`, look up the
canonical width-four digit. Use it if its seed point is in a fixed
allowed set; otherwise use the canonical width-three digit. Both
choices make division by τ exact. The three width-three seeds map to
width-four seed indices `{0,1,3}`; six other seeds are optional.

The allowed set is chosen **once**, before held-out inputs, by
enumerating all 64 optional-seed masks over the frozen 32-case
`full-prep-result.json` training panel. The selection score is the
mean single-use generic `M+S` count for each mask, with every digit
seed actually used by that stream prepared, batch-normalized, and
unit-orbit expanded. One inversion is retained separately and is
common to the ordinary cases. Select the lowest total count, breaking
ties by smaller mask. Save the full training table and source hashes.
The held-out evaluator must use only the selected fixed mask; there
is no per-scalar mask search in its intended runtime path.

For a stream using seed set `U`, construct only the dependency closure
of those seed points in the nine-point Jacobian chain. The source
operation costs in `M+S` units are:

| Seed index | Coefficient | Required seeds | Cost to construct |
| --- | --- | --- | ---: |
| 0 | `1` | input base | 0 |
| 1 | `2` | 0 | 7 |
| 2 | `4` | 1 | 7 |
| 3 | `1+τ` | 0 | 17 |
| 4 | `2+2τ` | 3 | 7 |
| 5 | `1+2τ` | 4 | 11 |
| 6 | `2+4τ` | 5 | 7 |
| 7 | `2+τ` | 3 | 11 |
| 8 | `1−2τ` | 1 and 5 | 16 |

Normalize only the used constructed points: for `m>0`, batch
normalization costs `(7m−3)` `M+S` plus one inversion. Unit-orbit
preparation costs one multiplication per used seed. The generic
online formula for an all-affine orbit table is
`6*tau_steps − 2*paired_strides + 11*(nonzero_digits−1)` under
`S=M`, with the first accumulator insertion free. This is a model
of explicit generic formulas, not a native timing claim. The
dependency chain, digit selection, table lookup, and normalization
control flow must be charged in a later full implementation.

Freeze `hybrid_subset.py` and this protocol before producing the
training receipt. Freeze the selected mask and held-out checker
before deriving any fresh scalar inputs. Verify exact ring
reconstruction and all elliptic-curve outputs. Compare with both
pure width-three and pure width-four controls on the same fresh
base/scalar pairs, preserving raw failures and source hashes. The
mixed-window idea and any academic novelty claim require separate
prior-art review; this test makes no novelty or CPU speedup claim.
