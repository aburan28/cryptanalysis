# Q1499: full-chain N83 continuation reaches 2²⁰ branches on four ordinary cells

The frozen Q1497 solver was allowed to continue after its first complete S3
pair for two leaf-polarity masks on each of the selected and holdout ordinary
N83 points. Phase 49's first pair is outside the exact factor base; phase
50's first pair has both leaves in the base. Every run entered search,
reproduced its archived first-pair bits and counters, and reached the
solver's existing 1,048,576-branch cap with exit code 42. The status for
each run is `BRANCH_CAP_SEARCH_STARTED`.

| Input | Phase | First pair usable | First-pair CNF/XOR calls | Last checkpoint CNF/XOR calls | Exploratory wall, s |
| --- | ---: | --- | ---: | ---: | ---: |
| selected | 49 | no | 94,498 | 751,222,500 | 9.45 |
| selected | 50 | yes | 96,790 | 721,644,871 | 8.78 |
| holdout | 49 | no | 96,822 | 751,224,824 | 9.60 |
| holdout | 50 | yes | 99,114 | 721,647,195 | 8.21 |

The final checkpoint cost is 7,281–7,950 times the first-pair cost in these
four fixed runs. It includes all work before the cap, including the first
pair. The runs had 30-second CPU, 31-second hard CPU, and 60-second wall
limits; the internal branch cap stopped them first. Wall values are
exploratory because there is no host isolation receipt. The Darwin child RSS
field in each receipt is cumulative and is not a per-process peak.

The [protocol](protocol.json), [freeze](freeze.json), [drive](drive_receipt.json),
[result](result.json), and per-run logs and receipts bind the exact curve
`EC1N83Ckb1h876c2921cb64`, actual B=30,977,592 base points, K=186,612
folded columns, two ordinary workloads, binary and XCNF hashes, masks,
limits, statuses, and branch/work checkpoints. The stage is `PDP4sat`, with
null IC candidate/run IDs and `isogeny: "none"`.

These capped rows establish a continuation-work boundary on the frozen
masks. They do not estimate natural complete-relation yield or rank novelty;
both remain unmeasured, and the fully charged N131 exponent stays null. The
next implementation should attack the complementary second-pair search,
then replay any full relation against the group law and exact base before
rank insertion.
