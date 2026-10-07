# Frequency-selected representatives for the joint Eisenstein table

The [joint radix-16 table](JOINT_WINDOW4.md) has 71 six-unit digit orbits.
Its original map always stores the lexicographically smallest point of each
orbit. This experiment stores a different point from the *same orbit* when
that choice makes common raw digits need only a sign change. The online
evaluator still uses one table point and at most one mixed addition per
nonzero joint digit. A sign change negates `y`; the other unit actions
multiply `x` by a cube root of unity. The per-curve map therefore changes
the frequency of those field multiplications without changing the recoder.
It is variable-time and intended only for public scalars.

The [selection producer](make_joint_window4_hot_design.py) counted raw digits
on the eight cases in the earlier frozen joint-window fixture. For each orbit,
it chose the unit representative maximizing the observed frequency of the
representative and its negative, with a lexicographic tie break. The producer,
[selected representatives](joint-window4-hot-design.json), and [fresh-input
generator](make_joint_window4_hot_inputs.py) were committed as `47ad2255`
**before** the new scalars were generated. The [new fixture](joint-window4-hot-inputs/inputs.json)
has 32,768 scalars across eight cases and excludes the nine prior fixtures.
Selection is curve-specific and bound to the exact `p`, `b`, and subgroup
order; unsupported curves reject the selected mode.

The [release](joint-window4-hot-native-panel.json) and
[warnings-as-errors UBSan](joint-window4-hot-ubsan-panel.json) panels each
have 24 arms in rotating order: selected, lexicographic, and fixed comb9.
Every native arm independently verified all 4,096 outputs per case. An
independent Python model checked all 32,768 scalar identities and 184 group
outputs. The generated action map covers every one of the 256 raw digit pairs
on both curves, with each selected representative checked against the original
orbit. Prepared points are independently recomputed. Both builds passed the
`test_curve` suite with 2,311,976 checks. No held-out case fell back to the
generic multiplier. The seven-position large-curve coverage remains
empirical; the conservative lattice bound in [JOINT_WINDOW4.md](JOINT_WINDOW4.md)
does not establish universal coverage.

The counts below aggregate four held-out cases, or 16,384 scalar
multiplications, per curve. Preparation counts are per prepared base point.
The diagnostic score is `16·online mixed additions + 8·online doublings +
online unit rotations`; it omits lookup, recoding, memory traffic, and other
field costs.

| Curve | Mode | Point slots | Static map bytes | Prep additions | Online additions | Online doublings | Unit rotations | Score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | selected | 284 | 1,308 | 308 | 55,063 | 0 | 25,105 | 906,113 |
| `glv-j0-32` | lexicographic | 284 | 654 | 340 | 55,063 | 0 | 43,193 | 924,201 |
| `glv-j0-32` | fixed comb9 | 512 | 0 | 502 | 48,945 | 32,674 | 0 | 1,044,512 |
| `j0-56` | selected | 497 | 1,308 | 560 | 114,233 | 0 | 57,253 | 1,884,981 |
| `j0-56` | lexicographic | 497 | 654 | 595 | 114,233 | 0 | 85,834 | 1,913,562 |
| `j0-56` | fixed comb9 | 512 | 0 | 502 | 114,187 | 98,214 | 0 | 2,612,704 |

The selected table removes 41.9% and 33.3% of the lexicographic table's
online unit rotations on the two held-out curves. Its diagnostic score falls
by 2.0% and 1.5%, respectively. The selected map is 654 bytes larger because
both curve-specific maps are compiled into the binary. These are verified
operation results, **not a controlled CPU speedup**. Local macOS timing fields
are retained only as exploratory raw data. No one-target DLP or rho speedup
is claimed by this repeated public-scalar workload.

The [isolated manifest producer](make_joint_window4_hot_isolated_manifest.py)
binds the same binary, exact fixture, both modes, hashes, and expected point
digests to the repository's serial service. The manifest schema validates
locally; a qualifying physical Linux host receipt is still needed before any
CPU timing ratio can be promoted. The implementation is a workload-selected
choice of representatives within the known joint Eisenstein digit format.
It carries no claim of academic novelty. The prior-art discussion and links
are in [JOINT_WINDOW4.md](JOINT_WINDOW4.md).
