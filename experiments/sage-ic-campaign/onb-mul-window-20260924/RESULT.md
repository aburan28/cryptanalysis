# Result: density-aware ONB multiplication

The accepted field source is SHA-256
`12bd1f54d807456f30a421acc8ae69614842f5bce174962b904547378e6493f0`.
Only `Onb.mul` changes relative to the prior PR. The method computes exact
cyclic rotations and XORs as before; the four-bit window groups nearby
rotations and the sparse route skips zero multiplier bits. A high-bit input
uses the original loop. The threshold of 12 set bits was frozen before the
accepted candidate's timing.

| Warm field stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 random multiplication | 1.04× | 1.05× |
| Degree 9 random multiplication | 1.05× | 1.04× |
| Degree 131 random multiplication | 2.25× | 3.05× |
| Degree 131 sparse multiplication | 13.08× | 32.68× |
| Degree 131 dense multiplication | 3.59× | 4.49× |

`benchmark.py` used 64 seeded operand pairs per case, 9 alternating paired
rounds, and 8 repeats per round. Ratios above use the separately recorded
median times from each side; raw JSON retains all case measurements.

| Degree 131 curve operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| `pointFromX` | 1.45× | 1.48× |
| `add` | 1.66× | 1.68× |
| `dbl` | 1.70× | 1.71× |
| `mul(P, 17)` | 2.07× | 2.43× |
| Unchanged `frob` control | 1.02× | 0.98× |

The curve-operation ratios are medians of 11 **matched old/new round ratios**
from `point_ops.py`. Each side used the same 48 seeded abscissae, the same
Euclid inverse and trace, and the same curve source. Earlier short-round
variants are retained because their unchanged Frobenius control had scheduler
outliers; the matched-ratio rule and longer rounds were frozen before the
accepted two runs. All point outputs matched exactly.

`verify.py` matched **3,087** original multiplication outputs: exhaustive
degree-5 coordinate pairs, random degree-9/131 coordinate pairs, raw
noncanonical bit patterns, high bits, negative left operands, zero, and one.
`Onb.selfTest` passed for degrees 5, 9, and 131. Five local IC tests that do
not need CryptoMiniSat also passed with the candidate field loaded first.

The first window-only candidate improved wide dense products but regressed
degree-5/9 controls and one sparse control. The accepted sparse/window
candidate cleared the frozen field gates. These are local Apple Silicon CPU
arithmetic-stage timings; this Python ONB path does not call Metal. A complete
index-calculus or DLP speedup is **unknown** because the local SAT solver
dependency is missing and there is no calibrated common operation unit or
verified recovered-log comparison for this change.
