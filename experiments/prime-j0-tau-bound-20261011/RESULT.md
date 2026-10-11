# Exact tau-only orbit cover removes the norm-seven stage

The radix-1024 secp256k1 scalar multiplier has a **73,417-seed exact
minimum tau-only cover** under the norm bound `N(digit) <= 1024^2`.
It uses the maps `1`, `tau`, and `tau^2` over twelve full windows and
needs no norm-seven `rho` branch. A native point replay on a new,
disjoint 4,096-scalar panel matched the independent control on every
case and separate binary multiplication on the first 128. The native
Rust suite passed **143/143 tests** and the release CLI passed all
**10** independently checked boundary cases.

## Exact cover theorem and construction

The six-unit quotient of the radix-1024 digit lattice has **174,764
classes**. Multiplication by `tau` permutes them in **513 cycles**.
A seed covers one, two, or three consecutive classes of its cycle;
the allowed length is fixed by whether its nearest representative has
norm at most `R^2`, `R^2/3`, or `R^2/9`. The nearest representative
dominates any other representative of the same class because the
successor classes are identical and `N(tau^j d)=3^j N(d)`.

On each cycle, the minimum seed count is the shortest partition into
eligible segments of lengths one through three. The constructor uses
the line recurrence after each of the three possible cuts that can
supply class zero. An independent verifier solves the cyclic Boolean
coverage constraints with a two-bit state dynamic program, recomputes
nearest norms and all cycles, and checks the resulting cover against
every **1,048,576 exact residues**. Both methods give **73,417 seeds**.
The [protocol](PROTOCOL.md) gives the recurrence and nearest-norm
argument; the [exact receipt](exact-check.json) binds the serialized
[cover](cover-tau-exact.bin) and verifier. The earlier tau-only greedy
cover used 78,253 seeds, so this exact construction removes **4,836
seeds** from that format.

For any `k` selected seeds, if `U` classes have no tau provider, adding
a direct seed for each such class completes a tau-only cover. Hence
`U >= 73,417 - k`. At the **67,338-seed** budget of the fixed rho
cover, at least **6,079 classes** must lack a tau provider. The
swapped fixed cover has 11,396 such classes, leaving a 5,317-class
gap to this lower bound. The bound applies to this radix, norm limit,
and one-seed-per-class format.

## Frozen paired scalar panel

The construction, serialized cover, independent exact verifier, and
panel tools were committed at `312a1a5c607cd6b404e1ee7a5a284eb82f285917`
before the new panel was generated. Its seed is `20261011235019`, and
the [input receipt](holdout-inputs.json) checks modular disjointness
against the listed earlier panels. The [path verifier](holdout-check.json)
checked every digit, seed, map, unit, terminal, scalar congruence, and
the first 128 binary point fixtures.

| Same 4,096-scalar panel | Seeds | Scalars using rho | Rho digits | Gauge rotations | Full-window nonzero terms | Retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Swapped fixed-budget cover | 67,338 | 2,272 | 3,242 | 19,969 | 49,152 | 54,339,936 |
| Exact tau-only cover | **73,417** | **0** | **0** | **18,447** | 49,152 | **59,032,928** |

The exact cover removes **2,272 norm-seven branch activations**, **3,242
rho-mapped digits**, and **1,522 gauge rotations** on this paired panel.
It adds **6,079 seed rows**, or 72,948 window point entries. Retained
memory increases by **4,692,992 bytes**. The DR20 atlas grows from
1,667,480 to **1,691,796 bytes**; the native
[atlas verifier](native-atlas-check.json) checked every class record
and inverse unit action. The [phase receipt](phase-cost.json) records
exact grouped-unit occupancy for both covers.

Using the frozen direct-XYZZ source-call model, the paired rho and
gauge subpath changes by `-20,448M -11,360S -6,066C`: one rho
branch activation costs `9M+5S+2C`, and one gauge rotation costs `C`.
Here `M` is a general field multiplication, `S` a squaring, and `C`
a fixed-constant Solinas product. This count excludes other evaluator
work, memory traffic, and CPU lookup behavior.

## Native replay and measurement boundary

The [native materializer](materialize_native.py) substitutes only the
tau-only DR20 atlas and its three size assertions in the direct-XYZZ
evaluator, then adds the frozen 4,096-case digit and point test. It
reuses the existing `rho0` backend slot, whose norm-seven branch is
never selected by this atlas. The [native receipt](native-check.json)
binds the generated Rust source, panel, atlas, raw suite log, and
**143 passing tests**. The [CLI receipt](native-edge-check.json)
binds the release binary and ten boundary outputs. Compressed raw
outputs are stored beside those receipts.

This establishes the exact table-size threshold for removing rho at
this radix and the paired operation/memory tradeoff. A CPU wall-time
comparison requires the host-level isolation and noise gates in
`../../docs/ISOLATED_BENCHMARKS.md`; online wall-time speedup is
currently unknown. The next fixed-budget search can use the 6,079
class lower bound to measure its remaining room for improvement.
