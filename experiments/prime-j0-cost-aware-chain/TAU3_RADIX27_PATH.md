# Direct radix-27 shortest-path τ recoding

The [six-step quotient atlas](TAU3_QUOTIENT_ATLAS.md) reproduces the frozen
width-three digit stream from 6,561 coefficient residue states. The [sparse
hot-pair table](TAU3_SPARSE_HOT.md) then pays one mixed addition for a
prepared orbit pair and two for a cold pair. This proposal chooses block
actions by their **actual cost in that sparse table**.

In the Eisenstein coefficient basis used by the native code, `τ⁶ = −27`.
For state `z = a+bτ`, a valid six-step action represents a correction
`C = c+dτ`. It can be used whenever `c ≡ a (mod 27)` and
`d ≡ b (mod 27)`, with exact successor `(C−z)/27`. Enumerating the frozen
343 orbit representatives under all six units, with the existing three-step
spacing rule, gives 2,053 distinct valid actions. The 729 coefficient
residue classes have 397, 222, and 110 classes with respectively one,
three, and nine candidate actions. Every class has at least one action.

For block `i` and current coefficient state `z`, define `D(i,z)` as the
minimum sum of mixed additions needed to reach zero within the prepared
block limit. Its recurrence is:

`D(i,z) = min_{C ≡ z (mod 27)} (charge_i(C) + D(i+1,(C−z)/27))`.

The charge is zero for the identity action, one for a single-digit or
prepared hot pair, and two for a cold pair. The terminal state costs zero;
nonzero state after the last prepared block is infeasible. Ties use smaller
correction coefficient `L1`, action code, then signed coefficients. This
finite shortest-path computation is exact for the declared action alphabet,
point table, and block bound. Every selected path reconstructs the input
coefficient pair because `z_i = C_i − 27 z_{i+1}`. The resulting scalar is
still congruent to the original scalar modulo the subgroup order.

The [Python screen](screen_tau3_radix27.py) is a **retrospective** feasibility
test on the older compact-pos fixture, which also contributed to sparse
hot-map training. It replays each selected correction and compares its
charged additions with the native sparse receipt. Its result cannot serve
as a prospective speedup measurement. A native evaluator must first prove
exact outputs, fallback behavior, and bounded memory and recoding work.
Then freeze a new disjoint scalar fixture before prospective comparison.

The [action-pool generator](make_tau3_radix27_map.py) packs each residue's
one to nine choices into an offset array and a four-byte option array.
Its [read-only audit](audit_tau3_radix27_map.py) regenerates the complete
map. All correction coefficients fit signed bytes; the map uses 9,672
compiled bytes. The source and generated table must be frozen before native
recoder integration.

This design makes no academic novelty or CPU speedup claim. Related
endomorphism recodings and shortest-path digit selection require a separate
prior-art review. Dynamic programming spends target-scalar-dependent CPU
work and memory; a group-operation saving alone does not establish a
faster scalar multiplication. The current browser session returned an
expired-token error, so no new literature claim is made here.

## Retrospective feasibility result

The [frozen screen receipt](tau3-radix27-screen.json) was replayed by the
[read-only audit](audit_tau3_radix27_screen.py). All 32,768 coefficient paths
terminated within the existing prepared block limits, reconstructed their
inputs exactly, and had zero modeled fallbacks. The shortest-path search
found fewer charged additions than the native sparse action stream in all
eight old point cases:

| Curve, four old point cases | Compact native additions | Sparse native additions | Radix-27 optimum | Saving vs sparse |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 62,323 | 53,425 | 52,451 | 1.82% |
| j0-56 | 134,062 | 120,896 | 113,144 | 6.41% |

These are **retrospective operation counts**, including data used to train
the hot pairs; the optimum is computed by Python rather than native point
multiplication. The search cache ended with 41,468 states on the smaller
curve and 254,295 states on the larger curve across four point cases. That
shared exploratory cache is not a native online memory measurement. A
bounded per-scalar native solver and a new disjoint fixture are still needed
before evaluating speed or prospective operation savings.

## Bounded native control and decision

The native recoder uses a per-scalar memoized shortest path with at most
1,024 states and a fixed 2,048-slot hash index. Because correction
coefficients have maximum absolute values 96 and 54, reachable states at
one depth differ by less than `192/26` and `108/26` in the two coordinates.
There are therefore at most 9 × 6 integer states at a depth and at most
864 over 16 depths. The prepared sparse point table and its generic fallback
are reused. The complete online interval includes the path search, its
53,312 bytes of stack scratch, and point evaluation. The added action pool
raises compiled static map data from 45,550 to 55,222 bytes.

The release curve suite passes 2,308,672 checks, including map reconstruction,
boundary scalars, forced fallback, identity, and 128 seeded exact-output
comparisons per study curve. The [old-data native
receipt](tau3-radix27-native-design.json) and [read-only
audit](audit_tau3_radix27_native_design.py) verify all 16 raw arms, 32,768
generic point outputs, zero radix-27 fallbacks, and exact equality between
Python-optimal and native additions in every case. Across four old point
cases, the native path explored 127,726 / 369,511 states and considered
247,900 / 906,805 options on the two curves.

The local, unisolated median online times were 1.3055 ms for sparse versus
2.8215 ms for radix-27 on `glv-j0-32`, and 2.8245 versus 8.2395 ms on
`j0-56`. These single executions on a contended host do **not** establish
controlled speed ratios. They are sufficient to flag substantial recoding
overhead for this implementation. The receipt keeps `cpu_timing_claim` and
`isolated_receipt` null. The next design task is to reduce online path
search cost before investing in a prospective speedup panel; the present
branch is an exact operation-bound control rather than a faster solver.

## Prospective operation gate

The [fixture generator](make_tau3_radix27_inputs.py) uses seed
`0x27A61C0B6E8F904D` and excludes every earlier scalar fixture, including
the sparse panel. Commit the generator, [fixture audit](audit_tau3_radix27_inputs.py),
[paired runner](check_tau3_radix27_panel.py), and [raw-result
audit](audit_tau3_radix27_panel.py) before generating inputs. Commit the
eight generic reference digests and scalar files before either candidate
arm runs. The paired sparse/radix-27 order alternates by point case.

The operation gate requires all 16 raw arms to match generic point outputs,
zero radix-27 fallbacks, the same prepared point counts, and strictly fewer
radix-27 additions in each of the eight cases. Keep all failures and
timeouts. Record DP states and options evaluated. The online interval must
include lattice reduction, the complete per-scalar path search, point
evaluation, and final affine conversion; point preparation and independent
scalar replay are separate. CPU ratios remain exploratory without repeated
paired runs and a host-level isolation receipt. A successful operation gate
does not override the native old-data latency warning.

## Prospective disjoint-panel result

The [new fixture](tau3-radix27-inputs.json) and its [read-only
audit](audit_tau3_radix27_inputs.py) confirm 32,768 scalars disjoint from
the earlier fixtures and eight generic reference output digests. They were
committed before either arm ran. The [raw paired
receipt](tau3-radix27-panel.json) retains every exit code, timeout, stdout,
and stderr; its [audit](audit_tau3_radix27_panel.py) passes all eight
predeclared operation gates. All 16 arms match their generic outputs and
the radix-27 path has zero fallbacks.

| Curve, four new point cases | Sparse additions | Radix-27 additions | Addition saving | Radix-27 DP states / options |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 53,458 | 52,402 | 1.98% | 125,286 / 242,270 |
| j0-56 | 122,431 | 113,820 | 7.03% | 371,173 / 914,167 |

The point tables remain 12,672 / 24,192 bytes on the two curves. The
radix-27 variant adds 9,672 static action-pool bytes and uses 53,312
bytes of online stack scratch per scalar. Local, unisolated medians over
four point cases were 1.7405 versus 2.9075 ms for sparse versus radix-27
on `glv-j0-32`, and 2.3620 versus 7.9785 ms on `j0-56`. These runs are
single executions on a contended host, so they are not controlled CPU
ratios; the receipt keeps the CPU timing claim null. The operation saving
also appears on this disjoint panel, while the measured work suggests the
search cost outweighs it in the current implementation. For this fixed
action alphabet and point table, the shortest-path values also bound any
further addition-only improvement to 1.98% / 7.03% relative to the sparse
recoder on this workload. A faster scalar implementation must reduce
recoding cost, improve point arithmetic, or change the action/table budget.

The native code and benchmark compiled under AppleClang with
`-DCA_SANITIZE=ON` (AddressSanitizer and UndefinedBehaviorSanitizer) and
`-DCA_WERROR=ON`. Two optional 4,096-scalar sanitizer replays were stopped
with exit 143 after the contended local host gave each process only about
3% CPU. They did not produce a pass or a diagnostic; sanitizer runtime
correctness remains unverified locally. The draft PR's CI sanitizer job is
the pending validation gate.
