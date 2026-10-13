# Count-based low-work gauge tree

The evaluator passed an unseen 512-scalar secp256k1 panel generated after
source commit `89761521a`. All three native schedules reproduce each
independent point with 7,680 group additions. The count-based tree matches
the serial schedule's 1,023 gauge rotations; the preceding greedy tree
uses 1,889. Its modeled work is 75,775 units, versus 76,641 for the greedy
tree and 77,823 for serial. Its modeled dependency depth is 29,240 units,
versus 25,296 for greedy and 77,823 for serial. Thus this plan reduces
modeled work by 2.63% and modeled depth by 62.43% against serial on the
same panel. The tree and greedy plans each retain 11,552,448 bytes; serial
retains 11,505,936 bytes. `comparison.json` binds the fixture, all 1,536
native rows, binary hashes, and model replay.

The count-based scheduler lowers modeled products plus rotations for the
frozen 4,096-scalar secp256k1 design panel from 613,140 under the preceding
greedy tree to 606,178, while retaining the same 61,438 group additions.
Its aggregate modeled dependency depth is 234,145, compared with 202,235
for the greedy tree and 622,562 for the serial schedule. The 46,512-byte
plan table has the same footprint as the preceding tree table. All 969
count patterns were independently replayed; 641 use less modeled work than
the preceding greedy plan.

On the earlier 512-scalar holdout, the model records 75,776 work units and
29,273 depth units, compared with 76,678 work and 25,299 depth for the
greedy tree and 77,824 for both work and depth in the serial schedule. The
native evaluator reproduces all 512 independently generated points and
matches the model's 7,680 additions and 1,024 rotations. It also reproduces
seven boundary scalar points. The binary, source, table, and calibration
hashes are in `native-receipt.json`.

The design and earlier holdout panels were known during schedule design;
their rows remain calibration controls. The product model excludes plan
lookup, memory effects, recoding, exceptional branches, and affine recovery.
Complete-operation CPU performance awaits an isolated host measurement.

An instrumented replay counted calls to the native Solinas multiplication
kernel, including squares, for every fresh holdout and boundary scalar. The
tree's join interval made **75,775 calls across 512 cases**, exactly the
modeled work total with zero per-case discrepancies. Affine recovery made
2,048 further calls, four per nonidentity point; no calls occurred between
case reset and the join interval. All seven boundary scalars matched their
modeled join count, including zero with no kernel calls. The counter is
limited to `u256_mul_solinas_with` and the single-threaded fixture CLI; the
binary inversion, integer recoder, table traffic, and wall time are separate
costs. `opcount-receipt.json` binds the instrumented binary, overlay, raw
rows, and per-case checker.
