# 20 B/s on one RTX PRO 6000: one block per SM, no denominator field

Question: [THROUGHPUT-20B.md](THROUGHPUT-20B.md) priced 20 B complete scalar
updates per second on one RTX PRO 6000 as out of reach for the table walk,
from a static profile that put the ALU pipe at 96–100% of its rate. Its own
Nsight receipt in [THROUGHPUT-29B.md](THROUGHPUT-29B.md) §5 disagreed: ALU
pipe 36–39%, carry-less unit 63–71%, issue slots 51%, one eligible warp per
scheduler. Which one is the kernel, and does the answer move the number?

Answer: **the Nsight reading.** The kernel is bound by how continuously the
carry-less unit is fed, not by ALU issue, and two things starved it: the
audited geometry ran with 28 KB of L1, and the reverse pass re-read a
denominator field it could rebuild. Fixing those and letting ptxas see the
products gives **20.078 B/s median** (five alternating samples,
20.077–20.080) against **17.406** for the tree's best previous configuration
measured in the same session on the same card, **+15.3%**, with 300 of 300
device reports re-walked by the host reference and the same distinguished
points as the unmodified kernel. The build is `make gpu-rtx-pro6000-20b`.

Everything below was measured on one RTX PRO 6000 Blackwell Server Edition
(188 SMs, 128 MB L2, 80 MiB persisting-L2 cap, 2.32–2.42 GHz under load,
never at its 600 W limit), driver 595.91 (CUDA 13.2), compiled with nvcc and
ptxas 13.3.73 from NVIDIA's pip wheels, host gcc 13.3, `sm_120` only. The
timed command is the tree's: `--curve 131 --packed --bench --steps 1024
--launches 32 --verify 0` at the automatic worker count (96,256 threads × 16
slots); the final row used `--launches 64`. Hardware counters are locked on
this host (`RmProfilingAdminOnly`), so the profile below is `clock64()`
phase timing built into the kernel (`PHASE_PROFILE=1`) plus CLMAD
microbenchmarks.

## 1. Boundary

Unit: billions of complete scalar updates per second, `finished:` line.

**Floor (derived):** the carry-less unit. Measured here on this card,
`CLMAD.LO`/`CLMAD.HI` execute at **1.62 lane-CLMADs per SM-clock** no matter
how many warps are resident (4 to 32 per SM), how the instructions are spaced,
or whether the operands are 32 or 64 bits; latency is 60 cycles and one warp
cannot issue more than one CLMAD per ~63 cycles even with sixteen independent
chains; ALU work co-issues at no cost up to ~50 LOP3 per SM-clock. The kernel
issues **33.1 CLMADs per update** (28.9 in the 4.81 products, 3.0 in the
inversion's eight products, 1.25 in its ONB squarings; the squaring of λ is on
the ALU), which is **20.4 SM-clocks per update**, or **22.3 B/s at 2.42 GHz
with the unit never idle**. No lever in this note changes that count; every
row below is engineering, and its ratio to this floor is bounded above by 1.

**Reference:** table walk + byte pivot + pair-ILP + L2 persist + slot unroll 2
+ ALU squaring, 256 threads × 2 blocks per SM — the 17.298/17.414 B/s
configuration of THROUGHPUT-20B/29B — rebuilt here: **17.406 B/s** median of
five (17.12–17.41). The shipping σ-walk preset rebuilt here: **14.00** (its
receipt: 14.41–14.64).

## 2. The single table

Medians of three alternating repetitions unless noted; every row is the
reference's flags plus what the row names. B = batch 16 unless noted.

| variant | threads × blocks | B/s | / 22.3 floor | / 17.406 | verified | class |
|---|---|---:|---:|---:|---|---|
| shipping σ-walk, audited preset | 256×2 | 14.00 | 0.63 | 0.80 | receipts | before |
| table walk + byte pivot | 256×2 | 15.84 | 0.71 | 0.91 | receipts | before |
| **reference** (+ pair-ILP, L2 persist, unroll 2, ALU square) | 256×2 | **17.406** | 0.78 | 1.000 | receipts | reference |
| reference | 256×1 (8 warps) | 17.40 | 0.78 | 1.00 | | geometry |
| reference | 384×1 (12 warps, 170 regs) | 17.67 | 0.79 | 1.02 | | geometry |
| reference | 384×2 (85 regs, 76 B spill) | 16.70 | 0.75 | 0.96 | | geometry |
| reference | 768×1 (85 regs, 76 B spill) | 16.60 | 0.74 | 0.95 | | geometry |
| reference | 1024×1 (64 regs, 176 B spill) | 10.70 | 0.48 | 0.61 | | geometry |
| **reference** | **512×1** | **19.04 – 19.21** | 0.86 | 1.10 | 300/300 | **engineering** |
| 512×1, addend table in global | 512×1 | 18.91 | 0.85 | 1.09 | | did not pay |
| 512×1, L2 persist off | 512×1 | 18.01 | 0.81 | 1.03 | | persist worth +5.5% |
| 512×1, slot unroll 4 / unroll 1 | 512×1 | 18.73 / 18.78 | | | | did not pay |
| 512×1, batch 32 (157 MB blob) | 512×1 | 12.99 | 0.58 | 0.75 | | did not pay |
| 256×1, batch 32 (78 MB blob) | 256×1 | 13.14 | 0.59 | 0.75 | | did not pay |
| 512×1, batch 24 | 512×1 | 18.31 | 0.82 | 1.05 | | did not pay |
| 512×1 + `PAIR_CLMUL` / `CLMUL_FLAT` / `TOP_HOIST` / pair-ILP off | 512×1 | 19.08 / 18.91 / 19.03 / 19.10 | | | | neutral (vs 19.09) |
| 512×1 + `FROM_REDUCED` | 512×1 | 19.21 | | | | +0.6% (vs 19.09) |
| **512×1 + `TABLE_TAG_DENOM`** (§4) | 512×1 | **19.43** | 0.87 | 1.12 | 300/300 | **engineering** (vs 19.14) |
| + `ALU_SQR` (−1.25 CLMAD/update) | 512×1 | 19.36 | | | | neutral |
| + `TABLE_FUSED` (§5) / + `FUSED_PIPE` | 512×1 | 19.22 / 19.42 | | | 300/300 | neutral |
| 256×1, batch 32, tag denominators / fused | 256×1 | 16.49 / 18.21 | | | | did not pay |
| **+ `INLINE_POLY=3`, unroll 1** (§6) | 512×1 | **19.87** | 0.89 | 1.14 | | **engineering** |
| + `TABLE_PIPE_SELECT` (§6) | 512×1 | 19.95 | | | | +0.4% |
| + `PACKED_CHAIN_FIRST` | 512×1 | 20.00 | | | | +0.2% |
| **+ `FROM_REDUCED` = `make gpu-rtx-pro6000-20b`** | 512×1 | **20.078** (5 × 64 launches: 20.077–20.080) | **0.90** | **1.153** | **300/300, 472,776 DPs = reference's count** | **engineering** |
| the same, fused single pass instead of pipelined forward pass | 512×1 | 19.91 | 0.89 | 1.14 | 300/300 | engineering |
| the same in DP-34 collection (`--dp-weight 34 --dp-file`) | 512×1 | **19.04** vs 16.70 for the reference | | 1.14 | | engineering |

Reading the ratio column: the reference sat at 0.78 of the carry-less floor;
the 20.08 row is at 0.90, i.e. the unit is idle one clock in ten. The
remaining 10% is in the inversion (§7).

## 3. One block of 512 threads per SM

Same kernel, same 110 registers, no spills, same 16 warps per SM, same SASS:
`__launch_bounds__(512, 1)` in place of `(256, 2)` is **+9.4%**. The
difference is the shared-memory carveout. The table walk's 48,732-byte table
is per block; two blocks need 97 KB of the SM's 128 KB unified L1/shared and
leave **28 KB of L1**; one block needs 64 KB and leaves **64 KB**. The
`--prefer-l1` hint confirms the mechanism from the other side: it makes the
256×2 build fall to 13.7 B/s (the driver honours it by shrinking shared until
only one 256-thread block fits) and leaves 512×1 unchanged. Moving the addend
table to global memory to free still more L1 (18.91) does not pay, so 64 KB
is enough for what this kernel keeps hot: the compact state's tail-byte
planes shared by neighbouring warps, `hist`, `dead`, and the reverse pass's
re-reads.

More warps than 16 need fewer than 110 registers and spill (384×2, 768×1,
1024×1 rows); fewer warps lose latency hiding (256×1, 384×1). Batch 24 and 32
lose at every thread count, even with the 78 MB footprint of the tag
denominators (§4): the 512×1/B16 point is the optimum of this kernel's
register file × L1 × L2 window, and the inversion's 4.25 CLMADs per update are
the price of it.

## 4. `TABLE_TAG_DENOM`: no denominator field

The reverse pass needs `d = x + x_T` for each slot and was loading the 17
bytes the forward pass had stored. It also has to read `hist` (8 bytes) to
stay a class function, and the low 16 bits of `hist` are exactly this step's
tag, from which `x_T` is one 5-word shared read. So the denominator field goes:
−17 bytes stored and −17 loaded per update (−18% of state traffic), and the
persisting blob shrinks from x/y/pchain/denominators (105 MB, over the 80 MiB
window) to x/y/pchain (78.5 MB, entirely inside it). **+1.5%**, bit-identical
walk. This is also what turns the batch-32 rows from 13.1 into 16.5–18.2
B/s: at batch 32 the fields outside the window had been thrashing the 48 MB of
non-persisting L2 — but 16 warps at batch 16 still beat 8 warps at batch 32.

## 5. `TABLE_FUSED`: one pass per step

Montgomery's trick does not care in which order the batch is multiplied up,
only that the inverse chain runs back through the same order. So the reverse
pass of step *s*, holding the new point in registers, can run step *s+1*'s
selection and chain product on it before storing, accumulating in the order it
visits the slots; the next pass visits them in reverse. x and y are then
loaded once per update instead of twice (190 → 122 bytes per update), the
launch begins with one plain forward pass and ends with a pass that does no
selection, so the state left in memory is what the two-pass kernel leaves.
Verified 300/300 with the identical 472,776 distinguished points. Measured
**neutral** (19.22; 19.42 with the next slot's loads issued a slot early;
19.91 with inlined products): once the 64 KB L1 and the tag denominators are
in, state traffic is no longer what limits the kernel. Kept behind the knob
because it is what a larger batch would want (batch 32 fused: 18.2 against
16.5 two-pass).

## 6. Where the carry-less unit was idle

`PHASE_PROFILE=1` (lane 0 of every warp accumulates `clock64()` per phase),
512×1 + tag denominators, per warp per 16-slot step: **191,300 cycles =
forward pass 72,700 (38%) + inversion 30,000 (15.7%) + reverse pass 88,700
(46.3%)**. With four warps per scheduler the unit's share per warp-CLMAD is
4 × 76 = 304 cycles, so a fully fed unit would spend 12 × 304 = 3,650 cycles
per forward slot, 18 × 304 = 5,470 per reverse slot and 68 × 304 = 20,700 per
inversion. Measured: **4,540, 5,540 and 30,000**. The reverse pass was already
unit-bound; the forward pass and the inversion were not.

The forward pass: every slot's twelve CLMADs sat inside a `__noinline__`
call, and the ~900 cycles of selection (`fromPolynomial`, weight, seventeen
byte lookups for the phase, seventeen for the pivot, the cycle rule) ran
after the call returned, so a warp fed the unit nothing during them, and the
four warps of a scheduler do this in step. Three changes, each bit-identical:

- `PACKED_INLINE_POLY=3` (existing knob) inlines the single and paired
  products so ptxas can schedule across them: **+2.3%** at this geometry (the
  audited geometry had kept them out of line for code size), 92–100
  registers instead of 110.
- `TABLE_PIPE_SELECT=1` issues slot *k*'s two products first, runs slot
  *k+1*'s selection while they are in the unit, and reduces afterwards, with
  the chain product `prod·d` — whose reduction gates the next slot — issued
  before `W = prod·e`, and W's reduction deferred by one slot: forward pass
  72,700 → 69,300 cycles, **+0.4%**.
- `PACKED_CHAIN_FIRST=1` does the same reordering for the reverse pass's
  pair: **+0.2%**.

The forward pass did not reach 3,650 per slot. What remains there is most
likely the shared-memory pipe: the selection issues ~54 `LDS` per slot per
warp, 34 of them random byte lookups that the tree measured at 9.2 lanes per
SM-clock, which puts the MIO pipe near 60% during forward passes; the
addend-in-global row says L1 is not the answer. A cheaper selection (fewer or
wider lookups) is the next forward-pass lever and was not built here.

Things that were built and did not pay, recorded so they are not rebuilt:
`ALU_SQR` (−1.25 CLMAD per update, neutral: the inversion's squarings are on
a latency-bound chain, not on the unit's critical path); a two-buffer form of
the pipelined forward pass without the deferred-W copy (116 registers,
slower); skewing the start of the warp groups that share a scheduler by a
quarter step to break lockstep (neutral, so lockstep is not what idles the
unit); slot unroll 4; `PAIR_CLMUL`; `CLMUL_FLAT`; `TOP_HOIST`.

## 7. What is left, priced

At 20.08 B/s the update takes 22.7 SM-clocks against the unit's 20.4: 90%.
The profile says where the other 10% is: the **inversion**, 30,000 cycles per
warp-step for 68 CLMADs (one per 440 cycles) where the slot loops issue one per
350. It is a chain of eight dependent products with a basis conversion and a
Frobenius network between each, ~4,000 instructions at an IPC of 0.13 for the
warp running it. Nothing in the warp can overlap it; only the other three
warps can, and they are in their own inversions at about the same time.
Splitting the batch into two chains would overlap two inversions but costs a
second inversion (+4.25 CLMADs per update, +13% on the binding unit): not a
route. A poly-basis inversion with table-driven Frobenius maps would shorten
the chain's latency but its 17 lookups per map do not fit in shared memory
beside the walk table, and from global they cost more L2 traffic than the
state itself. The honest statement is that this kernel is at 0.90 of a
22.3 B/s floor and the remaining tenth is the latency of one serial inversion
per 16 slots.

## 8. Tooling notes

- `clmad` needs CUDA 13.3+; the 13.2 driver on this host runs the 13.3-built
  `sm_120` cubin under minor-version compatibility. The 12.8 `nvdisasm` and
  `cuobjdump` **silently drop** `CLMAD` from their listings (the addresses
  skip); use 13.3's, which shows `CLMAD.LO`/`CLMAD.HI` and, around each, the
  NOPs ptxas inserts to keep five issue slots between consecutive CLMADs
  (38 per paired product; the microbenchmarks show the spacing is harmless to
  unit throughput).
- `kernel_cost.py` reports per two updates when `ECC_UNROLL_SLOTS=2`, because
  the slot-loop bodies then cover two slots; halve its slot-loop rows.
- The engine prints the persisting window it actually got; with tag
  denominators it reads `78544896 of 78544896 field bytes, cap 83886080`.
