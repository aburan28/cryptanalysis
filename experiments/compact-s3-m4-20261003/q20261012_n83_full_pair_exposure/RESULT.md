# Q1500: 1,048,546 duplicate pair snapshots in each full N83 continuation

Keeping exact first-pair capture enabled through the solver's entire
1,048,576-branch cap shows why the Q1499 continuations spend so much work
after their first pair. On both ordinary N83 points, the phase-50 search
captured **one distinct complete first pair** and then recognized
**1,048,546 duplicate snapshots** of that pair. Capture did not overflow its
256-pair store. Both runs retained status `BRANCH_CAP_SEARCH_STARTED`.

| Input | Distinct complete first pairs | Duplicate snapshots | Last CNF/XOR checkpoint | Exploratory wall, s |
| --- | ---: | ---: | ---: | ---: |
| selected, `2eb250a29072` | 1 | 1,048,546 | 721,644,871 | 15.13 |
| holdout, `394256b9f901` | 1 | 1,048,546 | 721,647,195 | 25.36 |

The binary differs from Q1497 in one source line: it retains Q1479 capture
after branch 32,768. It uses the same exact N83 curve and B=30,977,592,
K=186,612 base, phase-50 mask, ordinary input archives, branch order, and
work cap. The unchanged CNF/XOR checkpoints match Q1499 exactly; the wall
values include the extra capture checks and are exploratory on this
unisolated host. The [freeze](freeze.json), [build receipt](build_receipt.json),
[drive](drive_receipt.json), [result](result.json), and per-run logs bind the
source, binary, inputs, first-pair bits, statuses, and counters. The stage is
`PDP4sat`, with null candidate/run IDs and `isogeny: "none"`.

Q1497's external restart panel exposed eight distinct first pairs in
769,426 CNF/XOR calls on the selected point. Q1500 spent 721,644,871 calls
while retaining one distinct first pair, about 7,503 times as many calls
per distinct first-pair output in these fixed panels. This comparison
identifies the search-order bottleneck; it does not estimate complete
relation yield. The next solver should hand a valid first pair to an exact
complementary-pair subsolver, then restart at pair level after that subsolver
finishes or reaches its declared cap.
