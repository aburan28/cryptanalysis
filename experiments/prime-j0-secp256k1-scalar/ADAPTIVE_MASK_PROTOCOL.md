# Per-scalar prepared alphabet: fresh validation protocol

The fixed mask 31 failed to show a reliable holdout gain. A retrospective
screen on the 64 fixed-hybrid holdout cases found a 22.28125 `M+S` per-scalar
arithmetic *oracle* advantage for choosing among all 64 masks. Those 64 cases
are exploratory data and are not reused for the validation below.

Freeze this source and protocol before generating the next 64 inputs. For
each fresh secp256k1 one-use base/scalar pair, obtain the same short
`Z[tau]` representative used by the width-four control. Recode with every
mask from 0 through 63, score each using `hybrid_subset.model` (exact
factor-base point chain, selective batch normalization, orbit preparation,
paired tau strides and mixed adds), then select the minimum `(cost, mask)`.
Run the selected mask and full width-four mask 63 through explicit prepared
point construction and Jacobian evaluation. Independently verify each output
using Sage scalar multiplication. Save all per-mask model costs, selected
mask, complete operation counts, seed digests, result coordinates, source
hashes, and the checked Sage runtime receipt. Refuse to overwrite results.

The primary diagnostic is the paired `M+S` difference for one-use variable
bases, with one field inversion accounted separately. The model excludes
scalar reduction and recoding/search costs, allocation, cache behavior, and
wall time. Report the 64-mask search size and total recoded positions.
No CPU speedup or academic novelty claim follows from this diagnostic.
Promotion requires a native implementation with search cost charged to the
complete operation and an isolated host-level benchmark receipt.

The earlier [Xu et al. width-four method](https://eprint.iacr.org/2024/1906)
is the control. Per-scalar algorithm selection and width adaptation have
prior art; any new technical claim needs a separate literature audit.
