# Rebalancing the multiplier's combines onto the add pipe (rejected)

`PACKED_ADD_COMBINE=1` (`ECC_PACKED_ADD_COMBINE`) rewrites the last step of
`clmul32`, where the four masked class products are joined, as PTX integer
adds instead of ORs. The four operands are bit-disjoint, so the sum equals the
union; the host path adds too, and `make test-packed-network` checks it. The
motivation was the measurement in [THROUGHPUT-CEILING.md](THROUGHPUT-CEILING.md):
the packed kernel is bound by the integer/logic pipe, and the hardware probe
showed adds can partly co-issue with logic instructions.

It does exactly what was intended at the instruction level and loses at the
walk level, so it stays off. The default build is unchanged: the control
client here has the same 5,288-instruction walk kernel, opcode mix, 128
registers and 48-byte stack as the audited preset.

## Measurement

[benchmarks/add-combine/compare.py](benchmarks/add-combine/compare.py) built
the audited RTX PRO 6000 preset with the knob off and on (CUDA 13.0.48,
`sm_120`), ran both GPU arithmetic suites, the field-multiplication component
probe (control, candidate, control), then complete walk benchmarks alternating
control and candidate after one excluded warm-up. Every timed run completed
201,863,462,912 scalar updates with 192,512 workers on one GPU
(`GPU-24208432-db79-986b-f620-9b063c6ceafe`, driver 580.95.05). Raw receipt:
[benchmarks/add-combine/result.json](benchmarks/add-combine/result.json).

Static walk kernel (helpers embedded):

| | Control | Candidate |
|---|---:|---:|
| Instructions | 5,288 | 5,304 |
| `LOP3` | 2,926 | 2,786 |
| `IADD3` | 20 | 164 |
| 3-input / 2-input OR `LOP3` (`0xfe` / `0xfc`) | 72 / 96 | 0 / 48 |
| Registers / stack bytes / spill bytes | 128 / 48 / 52+52 | 128 / 64 / 76+76 |

Component probe, B field products/s (medians of five):

| Mode | Control | Candidate | Control again |
|---|---:|---:|---:|
| Polynomial product | 51.158 | 51.219 | 51.404 |
| Paired product | 52.413 | 52.306 | 52.418 |

Complete walk, B scalar updates/s, three alternating pairs:

| | Control | Candidate | Change |
|---|---:|---:|---:|
| Pair 1 | 6.890428 | 6.824458 | -0.957% |
| Pair 2 | 6.861515 | 6.807996 | -0.780% |
| Pair 3 | 6.854947 | 6.796829 | -0.848% |
| Median | **6.861515** | **6.807996** | **-0.780%** |

The candidate was slower in every pair. Both arithmetic suites passed and
both walks reported their build identity.

## Reading

Moving 144 static (about 185 per scalar update) combines from `LOP3` to
`IADD3` did not raise the multiplier's throughput at all, so in this
instruction mix the add path buys no extra issue capacity. What did change is
register allocation: ptxas can no longer schedule the combine into the
fused `LOP3` slots it used before, the walk frame grows from 48 to 64 bytes
and spill traffic rises by about half, and that costs the 0.8 percent. The
remaining ORs in the kernel (48 two-input, 259 fused AND-OR) are either
funnel-shift or mask fusions that would gain nothing from the same rewrite.
The lever described in THROUGHPUT-CEILING.md remains instruction removal.
