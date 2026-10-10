# Canonical-sector nearest-digit rule

Let `m=2^w=3q+r`, where `w` is 9 or 10 and `r` is 1 or 2. The
arithmetic-orbit proof identifies canonical residues `(a,b)` in row
`a=0`, `0<=b<=m/2`, and, for each `1<=a<=q`, in three intervals:

| Sector | Canonical range for `b` | Nearest digit |
| --- | --- | --- |
| I | `0 <= b <= q-a` | `(a,b)` |
| II | `q+1 <= b <= 2q+r-1-a` | `(a-m,b)` |
| III | `2q+r <= b <= m-1-a` | `(a,b-m)` |

In row zero, the nearest digit is `(0,b)` for `b<=q` and `(-m,b)`
for `q<b<=m/2`.

For `b>0`, every canonical pair satisfies `a+b<m`. The existing
four-corner rule evaluates `(a,b)`, `(a-m,b)`, `(a,b-m)`, and
`(a+m,b-m)` under the Eisenstein norm
`Q(a,b)=a²+3ab+3b²`, breaking equal-norm ties lexicographically.
Relative to `Q(a,b)`, the last three norm differences, divided by
`m`, are `m-2a-3b`, `3(m-a-2b)`, and `m-a-3b`.

In sector I, all three differences are strictly positive. In sector
II, `(a-m,b)` beats `(a,b)` because `m-2a-3b<0`, beats `(a,b-m)`
because their norm difference divided by `m` is `-2m+a+3b<0`, and
beats `(a+m,b-m)` by `ma>0`. In sector III, `(a,b-m)` beats
`(a,b)` because `m-a-2b<0`, beats `(a-m,b)` because the difference
divided by `m` is `2m-a-3b<0`, and beats `(a+m,b-m)` because that
difference is `2m-2a-3b<0`. The stated interval endpoints make every
inequality strict for `a>0` and `r` in `{1,2}`.

At `a=0` and `b>q`, `(-m,b)` beats `(0,b)` and `(0,b-m)`. It ties
`(m,b-m)` in norm; the old lexicographic rule picks `(-m,b)`.
For `b<=q`, `(0,b)` wins strictly. At `b=0`, the old four-corner
enumeration has different translated corners, and direct substitution
shows `(a,0)` is their unique minimum for `0<=a<=q`.

The canonical orbit, rank, and unit code are unchanged from mode 129.
Applying that unit to the digit above gives the same signed digit,
quotient, next window, selected point, and final sum by induction over
the fourteen windows. Exhaustive residue checks cover all supported
radices and the tie row.
