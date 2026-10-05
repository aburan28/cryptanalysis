# Implicit predecessor recipes for the tapered τ orbit table

The complete tapered table from PR #287 and the unit-folded graph builder
from PR #293 use the same online scalar multiplication. PR #293 stores an
eight-byte predecessor recipe for every orbit, adding 78,744 static bytes to
the smaller schedule and 717,360 to the larger one. This experiment derives
each edge from the existing correction and residue index during preparation.
The candidate still builds one point per orbit and uses the unchanged online
lookup. It is a preparation-memory tradeoff, not a claim of a new online
addition saving.

For each correction `C`, recode its exact Eisenstein coefficient once. Store
its nonzero digit count, highest digit slot, and highest digit position in a
two-byte temporary descriptor. During depth-ordered construction, compute
`P = C - τ^j d` by iterating τ on the highest digit `j` times. Look up `P`
in the existing residue index, apply the recorded unit to that orbit's
correction, and require exact equality to `P` and a parent depth one lower.
Then reuse the parent's projective point and add the shifted digit point.
Every identity is checked before use. The static recipe table is unnecessary
for a standalone implicit build; the paired benchmark binary may still
contain it because it also executes the reference arm.

The exact candidate gate freezes this protocol and an exhaustive Python
screen before native evaluation. Compare to the static graph builder on the
eight already frozen points in `orbit-graph-inputs.json`, alternating arm
order. Require all 32,768 candidate outputs to match generic multiplication,
all online counters and point-table bytes to match the reference, exact
agreement between Python and C for preparation additions, rotations,
descriptor bytes, recode calls, integer τ steps, index lookups, and exact
parent checks, and a full prepared-point table equality check for at least
one generator on each curve. Preserve raw failures. Do not claim a CPU
wall-time win without the physical-host isolation gate in
`docs/ISOLATED_BENCHMARKS.md`. Claim static memory savings only for a
standalone build that excludes the reference recipe header; report the
paired binary's actual inclusion separately. Public research scalars only.

Existing work on τ-adic digit sets and unit actions remains relevant prior
art; this protocol does not assert academic novelty.

## Frozen native panel

Draft PR #295 contained this protocol and exhaustive screen before the native
builder was evaluated. The eight-point paired panel verified all 32,768
implicit-arm outputs against generic multiplication and found identical
online operations and preparation curve additions/rotations to the static
graph builder. The Python model matched every C recode, digit scan, integer
τ step, index lookup, exact parent check, and descriptor byte count. A curve
test independently compared all 307,287 prepared entries for generators on
the two curves; its full run passed 1,030,895 checks.

| Schedule | Curve prep additions | Curve prep rotations | Extra implicit preparation | Temporary descriptor | Static recipe lookup bytes used |
| --- | ---: | ---: | --- | ---: | ---: |
| `(10,10,10,10)` | 39,096 | 44,453 | 39,368 recodes; 291,168 integer τ steps; 39,096 parent lookups | 19,686 bytes | 0 |
| `(12,12,12,8,8)` | 267,552 | 248,427 | 267,910 recodes; 2,382,300 integer τ steps; 267,552 parent lookups | 177,150 bytes | 0 |

The reference arm uses 78,744 and 717,360 static recipe bytes. The paired
benchmark executable contains those arrays even when running the implicit
arm, so this panel does **not** measure a smaller standalone binary or lower
resident memory. Its raw local setup times are exploratory and show no basis
for calling this a speed improvement. Keep the implicit arm opt-in while an
isolated host and standalone build are unavailable. Raw runs and hashes are
in `implicit-orbit-graph-panel.json`.
