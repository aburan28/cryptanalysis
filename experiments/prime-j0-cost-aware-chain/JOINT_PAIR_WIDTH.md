# Width of the bounded Eisenstein pair point record

The [bounded upper-pair table](JOINT_PAIR_TOP.md) stores each prepared
point in four field words: `x`, `y`, `βx`, and an identity flag. On the
two exact study curves, every one of the 11,061 nonzero pair-orbit
representatives maps to a nonidentity subgroup point. The
[design producer](make_joint_pair_width_design.py) checks all of them
against both subgroup orders. Multiplication by each pair-position
power of 256 is invertible modulo the odd subgroup order, so the
prepared points at every position are nonidentity too.

This experiment freezes two smaller formats while keeping the same
digits, orbit map, bounded upper table, and online group additions:

| Format | Stored words per point | Unit action cost |
| --- | ---: | --- |
| existing packed plane | 4 | `βx` stored; `β²x = −(x+βx)` |
| triple plane | 3 | same unit action, no identity flag |
| double plane | 2 | compute `βx` or `β²x` by one field multiplication when needed |

The [frozen design](joint-pair-width-design.json) used the earlier
bounded-top fixture for training. It was committed before a new
disjoint fixture was drawn. The table-size and online field-operation
predictions are:

| Curve | Point slots | Four-word bytes | Three-word bytes | Two-word bytes | Extra online field multiplications for two-word format, per 16,384 scalars |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 11,817 | 378,144 | 283,608 | 189,072 | 22,403 |
| `j0-56` | 33,393 | 1,068,576 | 801,432 | 534,288 | 44,929 |

Removing the identity flag is exact for these two subgroup tables. The
two-word format trades a smaller random-access table for online field
work. The comparison requires native correctness and matched inputs;
local CPU timings remain exploratory until a qualifying isolated-host
receipt exists. This is a public-scalar table-format experiment, not a
one-target rho or IC speedup claim.
