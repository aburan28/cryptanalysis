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
work. The three-word format retains the same online arithmetic as the
four-word format and removes 25% of its point-table bytes. The two-word
format removes 50% of those bytes, but its extra field multiplication
could outweigh the cache benefit.

The [fresh fixture](joint-pair-width-inputs/inputs.json) excludes every
scalar in fourteen earlier fixtures. The [release panel](joint-pair-width-native-panel.json)
and [warnings-as-errors UBSan panel](joint-pair-width-ubsan-panel.json)
each passed 40 native arms in rotating order over eight cases: the
three pair formats, packed single-window plane, and fixed comb9. Every
native arm verified the full prepared table and replayed all 4,096
outputs per case. The independent Python model checked 32,768 scalar
identities and 184 group decompositions. The C suite passed 2,312,551
checks in both builds, including corrupted-table detection and forced
fallback for each new format.

| Curve | Scalars | Pair additions, all formats | Online field rotations, two-word only | Three-word table bytes | Two-word table bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 16,384 | 32,721 | 22,368 | 283,608 | 189,072 |
| `j0-56` | 16,384 | 65,450 | 44,944 | 801,432 | 534,288 |

The 32- and 24-byte formats also matched in unit-action additions:
20,898 and 41,140, respectively. The 16-byte format replaced these
with the counted field rotations. All modes had zero fallbacks and the
same output digest for each paired case. These are operation and memory
measurements, not a wall-time speedup.

The [isolated manifest producer](make_joint_pair_width_isolated_manifest.py)
can compare either new format against the 32-byte pair format or the
packed single-window plane. Each generated manifest passed the local
runner schema check with 183 custody artifacts, eight cases, and 24
paired repetitions. A real Linux host must supply the CPU partition,
NUMA node, frequency and IRQ controls required by
[the isolation gate](../../docs/ISOLATED_BENCHMARKS.md). The local
macOS timing fields are exploratory; no isolated receipt or controlled
wall-time ratio exists yet. This is a public-scalar table-format
experiment, not a one-target rho or IC speedup claim.
