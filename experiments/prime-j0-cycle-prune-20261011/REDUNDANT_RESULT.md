# Redundant-slot augmentation lowers rho-only coverage to 6,194 classes

At the same 67,338-seed radix-1024 table size, 32 coverage-redundant slots
can be replaced by seeds that provide tau routes to previously rho-only
classes. The resulting cover has **6,194 rho-only classes**, 32 fewer than
the cycle-refined cover and **115 above** the exact 6,079 lower bound for
this budget. The construction changes neither the class count nor the
retained seed count.

The [augmenter](augment_redundant.py) considers every selected seed whose
full four-map offer is already covered by other seeds. For each such slot, it
chooses an unused candidate that maximizes newly tau-covered classes minus
tau classes that would lose their last provider. It performs only positive
changes, with deterministic tie breaks on digit norm, candidate index, and
slot. All 32 selected replacements improve the count by one class. The
resulting cover SHA-256 is
`a3d34bddeae775043d6ff2580fc5578047375e021e7c96508584824ab34401b2`.

The [independent verifier](verify_redundant.py) replays all 32 replacements
using separately implemented Eisenstein actions, checks that the removed seed
was redundant at each step, reconstructs the priority assignment, and checks
all **1,048,576 residues**. The [receipt](redundant-check.json) passed.

The source and cover were frozen in commit `9102e45` before any scalar panel
was drawn for this variant. A new disjoint scalar panel, native point replay,
and isolated CPU timing are subsequent measurements. The class count is an
exact cover result and does not depend on host timing.
