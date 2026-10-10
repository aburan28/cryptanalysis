# Sixteen-window placement screen

Moving the radix-512 window from the final position to the penultimate
position reduces the exact seed-point count by 3,009. The final radix-256
digit bound becomes 181, while the penultimate radix-512 bound becomes
512. The total retained payload plus 32-bit atlas codes rises by 79,392
bytes because the final radix-256 row needs a second atlas.

| Format | Point slots | Point payload | Atlas bytes | Sum before metadata |
| --- | ---: | ---: | ---: | ---: |
| Final radix-512 | 107,814 | 6,900,096 | 1,436,064 | 8,336,160 |
| Penultimate radix-512 | 104,805 | 6,707,520 | 1,708,032 | 8,415,552 |

The exact cycle-cover counts are 5,463 seeds for ordinary radix-256 rows,
21,847 for the radix-512 row, and 6,476 for the final bounded radix-256
row. The reordered digit sum and termination margin equal those of the
final-radix-512 format exactly. Raising the final bound from 181 to 182
fails the sufficient termination inequality. `screen.py` reconstructs
the class cycles and minimum covers; `screen-result.json` records the
source hashes and integer proof margin.

This screen retains the final-radix-512 format as the smaller 16-window
table under the current 32-bit atlas encoding. Narrower 17-window layouts
are the next storage frontier to test with the same complete cost model.
