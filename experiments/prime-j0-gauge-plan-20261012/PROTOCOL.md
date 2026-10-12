# Cached gauge-plan protocol

Format 172 uses the same secp256k1 subgroup, U14 sector-digit choices,
Karatsuba Solinas field kernel, and gauge-aware XYZZ tree as format 171.
The dynamic tree selector compares candidate subtree pairs at each join.
Its score depends only on each node's gauge, whether it is affine, and its
modeled product depth. Sort the selected leaves by gauge, and build the tree
plan once for every feasible `(count0,count1,count2)` with total at most 14.
There are 680 such triples. A compact table stores 13 join instructions,
rotation count, and product depth for each triple. Prepare this table before
the online timer, then execute its instructions with selected affine points.

The frozen 4,096-scalar panel is
`../prime-j0-sector-digit-20261010/fresh-inputs.json`. Recheck every point,
scalar selector field, and rotation count against format 171; compare the
first 128 points with independent binary multiplication. Exercise all 680
feasible gauge-count patterns using actual affine table points and compare
the cached and dynamic trees' complete point, rotation, and depth records.
Check table indexing is bijective and retained bytes include every stored
plan. Rebuild the release CLI and check all 129 independent fixture cases.

`screen.py` independently counts the dynamic pair-gauge score evaluations
over the frozen inputs and binds its output to the native test log. This is
an algorithmic control count; CPU wall-time ranking requires the isolated
benchmark host and a paired complete-operation run. The construction cost
of all 680 plans belongs to reusable preparation, outside the online timer.
