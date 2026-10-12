# Fixed-seed assignment priority screen

The `rho0` seed set is frozen at 67,338 entries. Many residue classes
have more than one valid representation under its four allowed maps.
Reassign each class to the available representation minimizing, in order:

1. whether the map is `rho`;
2. norm of the mapped digit;
3. map number;
4. seed index.

Keep the seed array and its order unchanged. This isolates assignment
cost from table size. Preserve a class's exact six-unit orbit, digit
norm bound `1024^2`, and native direct-class index. Recode the already
frozen 4,096-scalar design panel and record terminal-bound failures,
map terms, and active branch cases. Verify the packed atlas independently
over all 1,048,576 residues and replay points before native promotion.

The previously frozen 4,096-scalar native panel has been observed for
the prior `rho0` format. A native promotion of this new assignment must
use a newly frozen, disjoint scalar panel for its own acceptance result.
