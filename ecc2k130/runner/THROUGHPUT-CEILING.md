# Why one RTX PRO 6000 cannot reach 20 B iterations/s

Measured on 2026-09-10 with [benchmarks/hardware-limits/probe.cu](benchmarks/hardware-limits/probe.cu)
on one RTX PRO 6000 Blackwell Server Edition (driver 580.95.05, CUDA 13.0.48,
`sm_120`), raw output in
[benchmarks/hardware-limits/result.json](benchmarks/hardware-limits/result.json).
Every arithmetic chain the probe times is re-simulated on the host, so the
rates below come from instructions that executed and produced the right
answer. They are ceilings for this GPU, not walk throughput.

## Measured ceilings

Medians of five timed repetitions, 1,536 resident threads per SM, eight
independent chains per thread. The SM clock sustained during the probes was
2.28–2.33 GHz (maximum 2.43 GHz).

| Instruction stream | T lane-ops/s | lane-ops per SM-clock |
|---|---:|---:|
| `LOP3` | 27.08 | 62.1 |
| `IADD3` | 27.54 | 63.0 |
| `SHF` (funnel shift) | 26.81 | 62.5 |
| `PRMT` | 26.61 | 62.2 |
| `IMAD` (32-bit) | 27.12 | 62.3 |
| `IMAD.WIDE` (32x32 to 64) | 23.07 | 53.2 |
| `POPC` | 6.83 | 15.8 |
| `FFMA` | 23.93 | 54.7 |
| `LOP3` + `IMAD.WIDE` interleaved | 24.97 | 57.5 |
| `LOP3` + `FFMA` interleaved | 26.47 | 61.0 |
| `LOP3` + `IMAD` interleaved | 30.15 | 69.3 |
| `IADD3` + `FFMA` interleaved | 35.65 | 78.3 |

The integer and logic instructions this client is built from issue at about
64 lanes per SM per clock, half the SM's 128 cores. Only mixes that pair
adds or 32-bit multiplies with logic ops exceed that, and never by more than
about 25 percent. Wide multiplies share the pipe with `LOP3`; interleaving
them gains nothing.

| Memory | Measured |
|---|---:|
| Shared-memory 32-bit loads | 15.9 lane-loads per SM-clock (64 B/SM-clock) |
| L1-resident global 32-bit loads | 14.5 lane-loads per SM-clock |
| L2-resident streaming read (48 MB) | 17.0 TB/s |
| L2-resident streaming write / copy | 3.7 / 5.3 TB/s |
| DRAM streaming read (6 GB) | 1.53 TB/s |
| DRAM streaming write / copy | 1.47 / 1.44 TB/s |

Device: 188 SMs, 1,536 threads per SM, 65,536 registers per SM, 100 KB of
shared memory per SM (99 KB per block), 128 MB L2, 95 GiB of memory.

The earlier `mad.wide` primitive probe reported 14.05 T/s; this probe reaches
23.07 T/s for the same instruction with more resident warps. The higher
figure is the ceiling to use.

## The packed kernel is already at the integer-pipe limit

The audited preset (batch 32, 256-thread blocks, two blocks per SM, every
packed option, direct reducer) executes 4,328.125 instructions per scalar
update on its common path, 742.5 of them `IMAD.WIDE`, 2,926 of them inside
the field-multiplication helpers (path-weighted count of the CUDA 13.0.48
SASS from the direct-reducer assessment receipts in the working notes,
`outputs/walk-operation-sensitivity.json`). At the audited 6.905 B updates/s that is
29.9 T instructions/s, or 69–72 lane-instructions per SM-clock at 2.2–2.3 GHz:
the same rate the probe measures for the best logic/multiply mixes. The
kernel is throughput-bound on the integer datapath, which is why every
instruction-count reduction in the history translated almost one-for-one
into speed and every scheduling, cache-policy, occupancy and state-layout
experiment did not.

Consequences, using speed = 6.905 × 4328 / N for a kernel with N
instructions per update:

| Target | Instructions per update allowed | Comment |
|---:|---:|---|
| 20 B/s | 1,494 | fewer than the multiplication helpers alone need (2,926) |
| 15 B/s | 1,992 | still below the helper bodies |
| 10.2 B/s | 2,926 | everything outside the products free |

The 144 wide multiplies per product (five and 5/32 products per update)
cost 742.5 wide instructions at 53 lanes per SM-clock: 31 B/s if the walk
did nothing else, but the masking, Karatsuba, reduction and basis conversion
around them are LOP3/SHF work on the same pipe. No configuration of this
multiplier reaches 20 B/s; 10 B/s would need the entire non-product part of
the walk to disappear.

## A bitsliced rewrite cannot reach it either

The repository's generated bitsliced multiplier costs 8,859 fused LOP3-class
operations per 32 products (277 per product) including the normal/polynomial
basis transforms, near the best known bit-operation counts for
`GF(2^131)`. At 27.1 T lane-ops/s the pipe can execute at most 97.8 B such
products per second. Twenty billion updates per second need
20 × 5.15625 = 103 B products per second before the Frobenius selection,
weight, additions, inversion chain and state traffic are counted. The
multiplier alone exceeds the machine.

Per update the bitsliced walk needs roughly 1,540 lane-ops (1,428 in
products, about 110 for weight, jump selection, additions and bookkeeping),
so the absolute ceiling with perfect scheduling, zero spills and free memory
is 27.1e12 / 1540 = 17.6 B/s.

The bitsliced component kernels in the working notes show what is realistic.
The fastest, a warp-tiled schoolbook stream with zero spills, measured
35.98 B products/s while executing about 21,600 fused operations per 32
products (675 per product): 24.3 T lane-ops/s, or 90 percent of the pipe. So
bitsliced code can saturate the pipe; the problem is that every
Karatsuba variant with a competitive operation count spilled or fell back
to memory traffic, because 131-word operands, a 261-word product and the
Karatsuba temporaries do not fit 255 registers, and the operands cannot stay
in shared memory either (262 words per thread against 100 words available at
256 threads per SM). A register-blocked Karatsuba schedule that reached
300–350 operations per product at 80 percent of the pipe would deliver
62–72 B products/s, which is 11–13 B/s of walk after the remaining work and
state traffic. That is the realistic upper end of a from-scratch rewrite,
and it remains well short of 20.

State residency adds a second bound. Keeping x and y in L2 needs at most
about 4 M resident walks (33 bytes each); the packed preset runs 6.16 M and a
bitsliced engine at 48 K threads × 32 lanes × B slots keeps x/y in L2 only
for B ≤ 2, where the batch inversion costs 7.5 products per update instead
of 5.16. Streaming x/y from DRAM instead costs about 100 bytes per update,
1.5 TB/s at 15 B/s, which is the measured DRAM read ceiling.

## What would move the number

* Removing instructions from the packed common path is the only lever that
  has worked, and it is linear: each percent of the 4,328 is a percent of
  speed. The helpers are 68 percent of the path; a 10 percent gain needs
  about 430 instructions per update removed.
* The measured `IADD3`/`IMAD` dual-issue headroom (69–78 lanes per SM-clock
  against 62 for pure `LOP3`) suggested rebalancing disjoint-mask combines
  onto adds. Tried and rejected: moving every eligible combine to `IADD3`
  left the multiplier's throughput unchanged and cost 0.78 percent of walk
  speed through extra spills ([ADD-COMBINE.md](ADD-COMBINE.md)).
* Nsight Compute cannot run in the Modal environment; an EC2 G7e instance
  with the same GPU can profile the exact binary and confirm the
  `pipe_alu`/`pipe_fma` utilisation this document infers.
* The walk itself is at the known minimum of five multiplications plus one
  batched inversion per step; x-only and other schedules screened here cost
  more. Twenty billion updates per second on this curve therefore needs
  about three of these GPUs, as [aws/README.md](aws/README.md) already
  budgets.
