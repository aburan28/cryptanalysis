# Cost-aware Eisenstein representative search: frozen protocol

## Question and scope

For scalar multiplication on `y²=x³+b` over prime fields with a usable
order-three automorphism, can choosing the scalar's Eisenstein-lattice
representative by the **actual width-4 τ evaluation schedule** reduce group
operations compared with choosing the representative of smallest coordinate
`L1` norm? The supplied Xu–Yu–Han–Lu paper develops width-4 τ-NAF and its
tripling schedule. This experiment keeps that digit set and schedule fixed;
the proposed change is the representative-selection objective. Related
GLV lattice reduction and double-base chains already exist, so academic
novelty is **not** claimed by this protocol.

The source text supplied by the user has SHA-256
`8d20aca6b52c9b6d541e858bc97fe050528f4169c7283c8e2988042b2813d28e`.
The existing local τ implementation used as a reference has SHA-256
`128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`
for `src/ec_tau.c`. That implementation is not yet on `main`; this
standalone prototype does not change or depend on its build.

## Exact candidate

Let `ω²+ω+1=0`, `τ=1−ω`, and let `λω` be the eigenvalue of `ω` modulo subgroup
order `r`. A scalar `k` may be represented by any `η=a+bτ` with
`a+b(1−λω) ≡ k (mod r)`. The current implementation obtains a short lattice
basis, rounds the coefficients of `(k,0)`, searches the 25 offsets
`du,dv ∈ [-2,2]`, and chooses the minimum `|x|+|y|` in the `1,ω` basis.

The candidate searches **exactly those same 25 representatives**. It
recodes each with the existing width-4 τ digit table and chooses the one
with the minimum predicted prepared-evaluation cost:

`10 × tripling_count + 16 × mixed_add_count + 1 × unit_rotation_count`.

These weights are multiplication equivalents with `S=M`: 10 for the cited
tripling, 16 for a point addition, and one for a nontrivial `ω` coordinate
rotation. They are frozen modeling assumptions, not measured time. Ties go
to the baseline `L1` choice. Both arms use identical precomputed seed points
and the same width-4 digit table. The candidate evaluates 25 recodings
instead of one, so its scalar-recoding overhead may outweigh any saved
curve operations, especially for the 64-bit pilot curves.

## Frozen diagnostic panel

After this protocol and `run.py` are committed and the PR is opened, run
`python3 experiments/prime-j0-cost-aware-chain/run.py panel` once with:

- subgroup orders `51131959441`, `157632877033`, and `42111239174233`;
- both primitive cube roots modulo each order, found from seeds `2,3,...`,
  each satisfying `λω²+λω+1 ≡ 0 (mod r)`; the same scalar list is used
  for both roots;
- six boundary scalars `0,1,2,3,r−2,r−1` plus 10,000 scalars per order from
  Python `random.Random(20261004)`, consumed in the displayed order;
- 25 offsets per scalar, the exact digit table in `run.py`, and the weights
  above.

Retain the complete diagnostic summary in `panel.json`: better/tie/worse
counts, mean predicted cost for each arm, median and total saved weight,
source hash, and any failure. The selection criterion for further work is a
positive mean predicted saving for both roots on at least two orders and zero correctness
failures. This is a gate for a C implementation, **not** a CPU speedup claim.
Do not interpret a cost-model win as a wall-time win.

## Independent correctness and next gate

`run.py selftest` compares both recodings with ordinary point multiplication
on `F_97` j=0 controls of subgroup orders 13 and 103, including all scalars
in each subgroup and 1,000 extra seeded scalars. Every representative is
also checked for congruence modulo `r`, and every digit expansion is
reconstructed exactly in `Z[τ]`. The panel performs those algebraic checks
on every scalar and retains failures rather than counting them as wins.

If the diagnostic gate passes, implement the selection in the C scalar
path, verify its exact point output against the existing scalar API on the
registered curves, and compare full scalar multiplication including
recoding and preparation. Any CPU wall-time claim must use the
[isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md) or an
equivalent host-level receipt with paired inputs, failures, and source
hashes. A measured comparison belongs in a follow-up PR.

## Frozen-panel result (2026-10-04)

The protocol above was committed as `0722e112` and opened as PR #250 before
the panel was run. The complete machine-readable summary is [panel.json](panel.json).
Each row covers the same 10,006 scalars for the indicated order and examines
25 congruent representatives per scalar. All recodings reconstructed their
chosen representative exactly, and all representatives preserved the scalar
modulo the subgroup order. No panel failure or timeout occurred.

| Subgroup order | `ω` eigenvalue | Lower modeled cost | Mean baseline | Mean candidate | Modeled saving |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 51131959441 | 11367182710 | 4,069 / 10,006 | 196.92 | 191.15 | 2.93% |
| 51131959441 | 39764776730 | 5,356 / 10,006 | 185.91 | 176.10 | 5.28% |
| 157632877033 | 31861365824 | 6,257 / 10,006 | 195.74 | 185.47 | 5.24% |
| 157632877033 | 125771511208 | 6,051 / 10,006 | 195.58 | 185.57 | 5.12% |
| 42111239174233 | 1380964599821 | 6,260 / 10,006 | 239.28 | 229.14 | 4.24% |
| 42111239174233 | 40730274574411 | 3,514 / 10,006 | 241.75 | 236.65 | 2.11% |

There were no higher modeled costs because the selection set includes the
baseline and ties prefer it. Median saving was zero on two rows, so the
benefit is not uniform across scalars. The predeclared model gate passes on
all three orders and both roots. **Decision:** advance to native integration
and full scalar multiplication measurement. This panel supplies no wall-time
ratio: it omits the cost of 24 extra recodings and uses modeled field-operation
weights. The existing C τ path is still outside `main`, so production
integration must be based on its eventual reviewed source snapshot.

## Standalone native selector

[native.c](native.c) implements the same 25-coset search and schedule-cost
decision with signed 128-bit lattice arithmetic. It has no curve arithmetic
or timing path. [native_check.py](native_check.py) compiles it with C11,
`-O2 -Wall -Wextra -Werror`, compares its exact representatives and each
operation count against `run.py`, and writes [native-check.json](native-check.json)
with compiler, architecture, source hashes, and every check row. The native
check passed 1,764 paired scalars: all scalars on the two toy subgroup orders,
the six panel order/eigenvalue arms, and both eigenvalues of a near-`2^64`
order. This establishes implementation agreement and 64-bit input handling
for those controls; it is not a full elliptic-curve or timing measurement.
The search has scalar-dependent branches and work. It is intended for public
scalars in research and rho setup; a private-scalar API would require a
separate constant-time design and review.

The stacked C integration and its exact-output receipt are documented in
[INTEGRATION.md](INTEGRATION.md). It keeps the baseline prepared evaluator
available and adds the cost-aware choice as an explicit opt-in function.
The fixed-base positional τ table is a separate candidate with its own
prospective protocol and results in [POSITIONAL.md](POSITIONAL.md).
The one-inversion table builder and its separate preparation metric are in
[GLOBAL_BATCH.md](GLOBAL_BATCH.md).
The block-normalized output format for public scalar batches is in
[BATCH_OUTPUT.md](BATCH_OUTPUT.md).

The optional [table-aware hot-orbit format](TABLE_AWARE_HOT.md) compares the
two shortest equivalent Eisenstein representatives against the same bounded
point table. Its fresh 16,384-output panel verifies exactly and saves
5.61%–6.81% of mixed additions, while charging an extra online recode;
isolated CPU speed remains unmeasured.

The [demand-gated selector](GATED_TABLE_AWARE.md) recodes a second
representative only after a cold two-digit block or span overflow.
Its fresh 16,384-output panel retains 81.35%–99.88% of the always-two
selector's addition saving while skipping 32%–79% of second recodes;
CPU speed awaits an isolated host.

The [carry-steered eight-digit format](CARRY_STEERED_TAU8.md) changes the
carry to the next τ block when a cold two-digit pair has a one-addition
representative in the same residue class. Its frozen 16,384-output panel
verifies exactly and saves 5.63%–11.81% of online mixed additions versus
the ordinary hot table, with identical per-point setup and a 13,122-byte
static map. Isolated CPU wall speed remains unmeasured.

The [gated dual carry-steering format](GATED_DUAL_STEER.md) combines that
block rule with a second shortest lattice representative, recoding the
second only when the first leaves a cold block or overflows the prepared
span. Its prospectively frozen 16,384-output panel matches generic
multiplication and an independent operation model; it saves 1.72%–2.56%
more mixed additions than carry steering alone while recoding a second
representative on 5.96%–19.92% of scalars. A temporary RunPod CPU pod failed
the host isolation gate, so CPU wall speed and rho impact remain unknown.

The [tapered complete residue-orbit format](TAPERED_RESIDUE_ORBITS.md) uses
large complete τ windows followed by narrow tail blocks. Its fresh
16,384-output panel verifies exactly and saves 3.76%–3.94% online additions
on the smaller subgroup and 39.14%–39.16% on the larger one versus gated
dual steering. Preparation rises to 62,424 and 506,664 additions and the
prepared point tables reach 1.26 MB and 8.57 MB. This is a reused-point
batch diagnostic; isolated CPU speed and one-target rho benefit remain
unmeasured.

The [unit-folded orbit graph builder](ORBIT_GRAPH_PRECOMPUTE.md) constructs
the same tapered table through exact lower-depth predecessor points. Its
eight-point frozen panel verifies 32,768 graph outputs and reduces preparation
additions by 37.4% and 47.2% for the two schedules. Preparation rotations
also fall, while static recipes add 78,744 and 717,360 bytes. No controlled
CPU timing is available.

The [one-word orbit graph format](PACKED_ORBIT_GRAPH.md) stores each verified
predecessor recipe in 32 bits. Its eight-point panel matches all 32,768
generic outputs and both arms' operations while cutting recipe data nearly
in half: 78,744→39,426 bytes and 717,360→358,734 bytes. The paired binary
contains both formats; controlled CPU and standalone memory gains are
unmeasured.

The [affine-wavefront builder](AFFINE_WAVEFRONT.md) evaluates the packed
orbit graph breadth-first with batched affine inversions. Its eight-point
panel matches all prepared table entries and 32,768 generic outputs while
retaining the same graph-addition and online counts. It adds three or four
preparation inversions and 157,488 or 1,417,200 scratch bytes. Isolated
preparation time and single-scalar latency are unmeasured.

The [bounded τ-tail shortest-path oracle](TAIL_ORACLE.md) recodes only a
small-coefficient tail using a 49,923-byte offline action table and the same
prepared seed points. Its frozen 32,768-output panel matches generic
multiplication, saving 7.48%–7.75% weighted evaluation operations on
`glv-j0-32` and 2.84%–2.98% on `j0-56`. A second online recode is charged;
isolated CPU speed and impact on rho remain unknown.

The [pre-gated τ-tail arm](TAIL_GATE.md) moves the oracle-versus-canonical
choice into a 6,241-byte offline bitset and emits the selected digit stream
once. Its genuinely disjoint 32,768-output panel verifies exact mode-3/mode-4
digit and operation agreement while retaining the original modeled saving.
The first attempted fixture was invalidated because its seed permuted the
older files; both the failure and replacement are recorded. Isolated CPU
speed is still unknown.

The [two-digit τ-pair shortest-path format](TAIL_DOUBLE_PAIR.md) permits a
second prepared digit in selected τ pairs to trade additions for fewer
triplings. Its disjoint 32,768-output panel verifies exact scalar recovery
and saves another 2.39%–2.49% weighted evaluation operations on `glv-j0-32`
and 0.99%–1.04% on `j0-56` beyond the one-digit tail oracle. It adds no
prepared points but increases static policy data to 106,087 bytes. Isolated
CPU speed and rho impact are unmeasured.

The [sign-folded packed two-digit policy](TAIL_DOUBLE_FOLD.md) stores one
representative of each `z`/`-z` state pair and uses phase-local 10-bit action
codes. Exhaustive state checks establish the same optimal modeled score and
gate decisions; a regression replay on the existing 32,768 scalar-point
inputs matches outputs and operation counts. Active policy data falls from
106,087 to 37,918 bytes. An isolated paired run is needed to learn whether
the extra decode work and smaller table improve CPU wall time.

An [8-bit residue-local encoding](TAIL_DOUBLE_FOLD.md#residue-local-byte-format)
of the same sign-folded policy brings active data to 31,660 bytes. It keeps
the same modeled evaluation score; the extra residue calculation leaves the
CPU wall-time ordering unresolved until isolated paired measurement.

The [orbit-pair point dictionary experiment](TAIL_PAIR_FUSED.md) goes further:
the 727 exact two-digit pair contributions form 121 sign/unit orbits. One
prepared affine point per orbit evaluates a two-digit pair with one mixed
addition. Its disjoint 32,768-output panel lowers modeled evaluation cost
5.49%–5.66% on `glv-j0-32` and 2.17%–2.23% on `j0-56` beyond the two-digit
arm, with point setup reported separately. Isolated CPU speed and rho impact
remain unmeasured.

The [phase-complete pair table](PHASE_COMPLETE_PAIR.md) expands those 121
orbits into 726 exact signed/unit points so the online pair evaluator performs
no rotations. Its separate disjoint 32,768-output panel verifies every output
and prepared point and saves another 1.59%–1.66% in the weighted evaluation
model. The table grows to 23,232 bytes; isolated CPU speed remains unknown.

The [high-order exact-pair search](GLOBAL_PAIR_SEARCH.md) explores a different
recoding policy over the same complete table. On reused design scalars, a
bounded-tail oracle plus a 32-choice, width-one high-order beam lowers the
modeled group-operation score 7.93% and 3.39% against its canonical-plus-oracle
comparator. The beam also evaluates 63 and 195 trial digits per scalar on the
two curves, plus canonical completions. A norm-greedy rule loses nearly all
the modeled gain. These are exploratory operation counts; no native or
isolated CPU speedup is established.

The [periodic 3-adic pair atlas screen](PERIODIC_PAIR_ATLAS.md) compiles a
bounded-oracle action into a lookup indexed by coordinate residues modulo
`27`. A per-scalar gate selects its schedule only when the complete modeled
group-operation score beats the canonical-plus-oracle schedule. On reused
design scalars, the gated policy saves 4.40% on `glv-j0-32` and 2.72% on
`j0-56` with about 3.6 and 13.5 atlas lookups per scalar, respectively.
The ungated schedule regresses on both curves. Native end-to-end speed and
academic novelty remain unproved. The
[prospective native protocol](PERIODIC_PAIR_NATIVE_PROTOCOL.md) fixes the
modulus-27 gate and disjoint comparison before new inputs are generated.
Its native old-design controls match all 2,048 Python word streams. The
[frozen disjoint panel](PERIODIC_PAIR_NATIVE_PROTOCOL.md#frozen-disjoint-panel-result)
verifies 32,768 scalar-point outputs in eight paired cases and passes the
predeclared modeled-operation gate: the score falls 4.17%–4.48% on
`glv-j0-32` and 2.62%–2.70% on `j0-56`, with no schedule fallbacks.
The candidate's raw local interval was longer in seven of eight pairs;
without host isolation or repeated pairs, CPU speed remains unknown.

The [bounded 64-bit recoder](PERIODIC_PAIR_INT64.md) keeps the same
periodic-atlas words and point evaluator while replacing wide remainder
arithmetic in the online recoder. It matches all 2,048 frozen design word
streams exactly. A new disjoint, isolated CPU panel is required to learn
whether the lower recoding overhead improves wall time.
Its new disjoint 32,768-scalar fixture is committed before either
comparison arm runs; no isolated CPU result exists yet.

The [single-pass first-word gate](FIRSTWORD_PAIR_GATE.md) uses a 128-byte
bitset to choose one recoder before constructing any full schedule. On
older point-1 validation scalars, it saves modeled group-operation score
2.21% on `glv-j0-32` and 0.77% on `j0-56` against the single-pass
canonical arm. The native arm matches all 16,384 selected old-data word
streams and generic outputs. Its disjoint 32,768-scalar held-out panel was
frozen before execution and passed the predeclared operation gate in all
eight paired cases: 1.94%–2.13% modeled saving on `glv-j0-32` and
0.69%–0.87% on `j0-56`. A separate native replay matched all 32,768
selected held-out word streams. This is an operation-count result;
isolated CPU timing and academic novelty remain unestablished.

The [exact mixed-radix tail](MIXED_RADIX_TAIL.md) lets a bounded Eisenstein
state use τ², a single τ, or doubling, each with an exact digit from the
existing point catalog. Its shortest-path map covers all 16,641 bounded
states and is independently audited. On 16,384 older scalars, the full
canonical-high-plus-mixed-tail score is 6.49%–6.66% lower on `glv-j0-32`
and 2.47%–2.58% lower on `j0-56` than the canonical pair arm; it also beats
the earlier first-word gate's old-data score. Its later native evaluator
matched all 16,384 old-data action streams, and the disjoint held-out panel
passed its operation gate in all eight cases. Host-isolated CPU timing and
academic novelty remain open.

The [full-digit mixed-radix tail](MIXED_FULL_DIGITS.md) extends every bounded
radix to all 727 already available digits. Its new disjoint panel verifies
all eight cases and reduces the operation score 0.52%–0.57% on the smaller
curve and 0.22%–0.23% on the larger curve against the unit-restricted map.
The [conventional fixed-base comb control](FIXED_COMB_CONTROL.md) then replays
the same frozen inputs. With 512 point slots and no static action map, comb
has a 34.96% and 40.18% lower aggregate operation score than full-digit
mixed on the two curves. The older positional tau method scores below comb
but uses a larger prepared table. These comparisons are algorithmic
diagnostics; controlled CPU timing and a one-target rho speedup are unknown.
