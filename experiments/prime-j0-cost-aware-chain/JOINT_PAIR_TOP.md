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
pair-table fixture as training and was committed as `5c711be8` before
drawing the [new disjoint fixture](joint-pair-top-inputs/inputs.json). It
fixture. It predicts the **same** online addition counts as the full
pair table, with fewer prepared points:

| Curve | Full point slots | Bounded point slots | Full table bytes | Bounded table bytes | Bounded preparation adds per base |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 22,122 | 11,817 | 707,904 | 378,144 | 12,261 |
| `j0-56` | 44,244 | 33,393 | 1,415,808 | 1,068,576 | 34,461 |

The [release panel](joint-pair-top-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-top-ubsan-panel.json) each
passed 32 arms in rotating order: bounded-top, full-pair, packed
single-window plane, and fixed comb9. All native arms replayed their
4,096 outputs per case and verified their prepared point tables. An
independent model checked 32,768 scalar identities and 184 group
decompositions. The C suite passed 2,312,331 checks in both builds.

| Curve | Packed-plane online adds | Full-pair and bounded-top online adds | Saved online | Bounded point slots | Bounded preparation adds per base |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 54,954 | 32,725 | 22,229 (40.45%) | 11,817 | 12,261 |
| `j0-56` | 114,239 | 65,453 | 48,786 (42.71%) | 33,393 | 34,461 |

Each curve has 16,384 fresh public scalars over four base points. Both
pair modes had exactly the same online addition and unit-action counts,
with zero fallbacks. Compared with the packed single-window control,
the extra preparation-add count would break even at about 8,811 or
11,386 scalars per fixed base at the observed per-scalar addition rate.
These are addition-call diagnostics, not wall-time break-even points.
The [isolated manifest producer](make_joint_pair_top_isolated_manifest.py)
passes local schema validation with 168 source and fixture artifacts,
eight cases, and 24 paired repetitions.

The proof concerns the two exact study curves, their recorded GLV
lattices, and the frozen digit rule. Correctness and preparation
operation counts are verified locally; cache behavior and wall time
still require a qualifying isolated-host measurement. Local macOS
timing fields are exploratory and do not show a
reliable speedup. This public-scalar variant is not a one-target rho or
IC speedup claim.
