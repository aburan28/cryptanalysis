# Bounded upper-pair orbit table

The [unit-closed two-window scheme](JOINT_PAIR_HEX.md) prepares 11,061
nonidentity orbit points at **every** pair position. The highest pair
cannot use most of those points. This variant derives a bound on its
coefficient for every scalar, then prepares only the orbit points inside
that bound. The lower pair positions and online digit rule are unchanged.

Let the GLV kernel basis be `v1`, `v2`. Babai rounds each exact lattice
coordinate to the nearest integer. Its residue has `L1` norm at most
`(‖v1‖₁ + ‖v2‖₁)/2`. The existing radius-two reducer minimizes `L1`
over a set containing that Babai point, so this is also an upper bound
for its chosen residue. Both initial coordinates therefore satisfy
`|x|, |y| ≤ B0 = ceil((‖v1‖₁ + ‖v2‖₁)/2)`. Every digit in the frozen
unit-closed alphabet has coordinate magnitude at most 10, giving the
integer recurrence `Bnext = floor((B + 10)/16)` after one digit.

After all lower pairs have been consumed, this yields a bound of 27 on
both upper-pair coordinates for `glv-j0-32`, and 14 for `j0-56`.
[The producer](make_joint_pair_top_map.py) exhaustively recodes all
3,025 and 841 coordinate pairs in those boxes, respectively: every pair
terminates in two digits, and every nonzero coefficient maps to one of
756 or 210 global unit orbits. The top representatives may lie outside
the box after a unit rotation; their maximum coordinate magnitude is 54
or 28, which the preparation builder must support.

The [frozen design](joint-pair-top-design.json) used the previous
pair-table fixture as training and was committed before drawing the new
fixture. It predicts the **same** online addition counts as the full
pair table, with fewer prepared points:

| Curve | Full point slots | Bounded point slots | Full table bytes | Bounded table bytes | Bounded preparation adds per base |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 22,122 | 11,817 | 707,904 | 378,144 | 12,261 |
| `j0-56` | 44,244 | 33,393 | 1,415,808 | 1,068,576 | 34,461 |

The proof concerns the two exact study curves, their recorded GLV
lattices, and the frozen digit rule. Correctness, preparation cost,
cache behavior, and wall time still require native and isolated-host
measurements. This public-scalar variant is not a one-target rho or IC
speedup claim.
