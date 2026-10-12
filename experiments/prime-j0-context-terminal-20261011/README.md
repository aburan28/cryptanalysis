# Exact terminal-pair bound for all four scalar corners

The current four-corner secp256k1 selector checks the coordinate-wise halves
of an out-of-disk terminal. This screen measures the largest point-work saving
available by changing **only the terminal pair** of the four nearest-plane
paths for each scalar in its frozen 4,096-scalar certificate. It permits any
two nonidentity entries from
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
midpoint split rule finds no option. [check_omitted.py](check_omitted.py)
reconstructs all of them through the frozen recoder. Of these, 1,856 have
terminal norm at least `4 × 149²`; the triangle inequality excludes any sum
of two points with norm below `149²`. The remaining 11 corners are checked
against the full table: six admit a pair, and none has a lower proxy than
the scalar's recorded choice. The [omitted-corner receipt](omitted-corner-check.json)
records each of the 11, including concrete witnesses where available.
Consequently **609,203 is the exact minimum over these four corners, their
fixed twelve full-window digit streams, and zero, one, or two entries from
the existing terminal table** on this panel. The screen is retrospective:
the panel was already used by the selector.

The 468-unit ceiling is small relative to the extra online search. A larger
operation reduction now requires changing the full-window digit schedule,
searching representatives beyond these four corners, or changing the point
table. Those are distinct candidate designs with their own correctness and
complete-operation measurement gates.
