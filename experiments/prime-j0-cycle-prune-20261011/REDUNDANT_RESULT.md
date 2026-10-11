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

The source and cover were frozen in commit `9102e45`, and the panel tool was
frozen in commit `be7233a` before drawing the new 4,096-scalar panel.
[Input](redundant-inputs.json), [path](redundant-paths.jsonl), and
[independent check](redundant-holdout-check.json) receipts bind the panel to
the cover and confirm disjointness from the listed earlier panels. The path
check validates every scalar congruence and computes 128 independent binary
point fixtures.

| Same fresh 4,096-scalar panel | Active rho paths | Rho digits | Full-window terms |
| --- | ---: | ---: | ---: |
| Cycle-refined | 1,441 | 1,735 | 49,152 |
| Redundant-slot augmentation | **1,435** | **1,720** | 49,152 |

Fourteen scalars switch from rho-active to tau-only, while eight switch in
the other direction. The net difference is six paths and fifteen rho digits
on this panel; it is a paired path diagnostic. Native point replay for the
new atlas and isolated CPU timing remain subsequent measurements. The exact
class count does not depend on host timing.
