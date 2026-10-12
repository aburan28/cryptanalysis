# Exhaustive terminal-pair bound for recorded scalar paths

The current four-corner secp256k1 selector checks the coordinate-wise halves
of an out-of-disk terminal. This screen measures the largest point-work saving
available by changing **only the terminal pair** of each path retained in its
frozen 4,096-scalar certificate. It permits any two nonidentity entries from
the existing 149-radius terminal table whose Eisenstein coordinates sum to
that path's terminal, including a two-point split of an in-disk terminal.
The twelve full-window digits, scalar representatives, point table, and proxy
weights stay fixed.

| Retrospective panel | Current selector | Best of all feasible terminal pairs | Saving |
| --- | ---: | ---: | ---: |
| 4,096 scalars, point-work proxy units | 609,671 | 609,203 | 468 (0.077%) |

The [screen receipt](screen.json) records 384,837,065 concrete nonzero point
pairs across 14,517 retained representative paths. It found a lower proxy on
294 scalars; 65 of those winning pairs split an in-disk terminal. The point
table has 80,521 entries including identity. [screen.py](screen.py) checks
the frozen input, path-certificate, and table hashes before enumerating pairs.
For each feasible pair it uses the table's exact exponent and unit labels to
recompute the bucket masks and proxy. It retains a concrete pair of table
coordinates for every improved scalar and hashes those witnesses in the
receipt. Pair selection, exhaustive search, and witness lookup are outside the
point-work proxy and would add online work in a native implementation.

The old certificate omits 1,867 of the 16,384 lattice corners when its
midpoint split rule finds no option. This screen does not reconstruct those
corners, so 468 units bounds terminal-pair improvements **within the 14,517
recorded paths**, not every possible four-corner scalar path. The screen is a
retrospective design diagnostic on a panel already used by the selector.

The measured ceiling is small relative to the extra search. The next design
step is to examine the omitted corners and, if they contain viable two-point
terminals, decide whether their point-work gain warrants a prospective
candidate. Changing full-window digits or the table layout is a separate
route to a larger gain.
