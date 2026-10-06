"""Q1403: the Q1325 implicit projected base with ordered raw leaves.

Sorting the four raw x masks removes their permutation symmetry without
changing the factor base.  A four-point group sum is permutation invariant;
the two intermediate S3 x coordinates are rebuilt for the sorted order.
The original Q1325 builder stays immutable for source-bound comparisons.
"""

from chain_s3_ordered import less_or_equal
from chain_s3_projected_sparse import build_projected_sparse_chain


def build_ordered_projected_sparse_chain(n, weight, target_x):
    formula, raw_leaves, projected_leaves, intermediates = (
        build_projected_sparse_chain(n, weight, target_x))
    for left, right in zip(raw_leaves, raw_leaves[1:]):
        less_or_equal(formula, left, right)
    return formula, raw_leaves, projected_leaves, intermediates
