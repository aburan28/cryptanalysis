# Compression and refill reaches 6,094 rho-only classes

A fixed-size radix-1024 scalar cover now uses **67,338 seeds** and requires
the norm-seven map for **6,094 of 174,764 classes**. The exact tau-only lower
bound at this budget is **6,079**, leaving a gap of **15 classes**. The
preceding redundant-slot cover uses 6,194 rho-only classes at the same seed
count, so compression and refill eliminate another **100**.

The [constructor](augment.py) replaces two selected seeds by one whose
four-map offers preserve complete coverage, then spends the freed slot on a
seed that adds tau providers. It ranks the resulting two-for-two exchanges
by their exact reduction in rho-only classes, rechecks coverage and the
objective after every accepted move, and records the ordered path. The first
pass accepted 100 moves; a complete second scan found no further improving
move of this form. The final cover SHA-256 is
`f5a88df0b9e08f39d2af4e8747cb1971c85b6afac94d652dfa55dbafb59b5261`.

The [independent verifier](verify.py) replays all 100 exchanges with
separately implemented Eisenstein actions, checks the intermediate
two-for-one coverage condition, reconstructs the priority atlas, and checks
all **1,048,576 residues**. Its [receipt](check.json) passed and binds the
source, path, input cover, and final cover hashes.

The construction was frozen in commit `659fb88`, and the
[panel tool](holdout.py) was frozen in commit `2c64acb` before drawing a new
4,096-scalar panel. Its [input](holdout-inputs.json),
[path](holdout-paths.jsonl), and [independent check](holdout-check.json)
receipts bind the source and cover hashes, establish modular disjointness
from the listed earlier panels, replay every scalar congruence, and compute
128 independent binary point fixtures.

| Same fresh 4,096-scalar panel | Active rho paths | Rho digits | Full-window terms |
| --- | ---: | ---: | ---: |
| Redundant-slot cover | 1,429 | 1,733 | 49,152 |
| Compression and refill | **1,403** | **1,696** | 49,152 |

Forty-eight paths switch from rho-active to tau-only, and twenty-two switch
the other way. The net reductions of 26 paths and 37 rho digits are paired
path diagnostics. Native point replay and controlled wall-time measurement
remain subsequent checks for this cover.
