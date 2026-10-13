# Count-based low-work gauge tree

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

These panels were known during schedule design. The next test is a new
disjoint scalar panel generated after the source freeze. The product model
excludes plan lookup, memory effects, recoding, exceptional branches, and
affine recovery; complete-operation CPU performance awaits an isolated
host measurement.
