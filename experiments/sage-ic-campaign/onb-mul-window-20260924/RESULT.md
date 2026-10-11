# Result: density-aware ONB multiplication

The accepted field source is SHA-256
`9cd0538466e7827ae5b07ecb01ab3592b47fbc03587ada93ef1000a150993298`.
Only `Onb.mul` changes relative to the prior PR. The method computes exact
cyclic rotations and XORs as before; the four-bit window groups nearby
rotations and the sparse route skips zero multiplier bits. A high-bit input
uses the original loop. The threshold of 12 set bits was frozen before the
accepted candidate's timing. `int.bit_count` is bound when available, with
the existing `popcount` helper on Python 3.9.

| Warm field stage | Paired run A | Paired run B |
| --- | ---: | ---: |
| Degree 5 random multiplication | 1.05× | 1.05× |
| Degree 9 random multiplication | 1.09× | 1.06× |
| Degree 131 random multiplication | 2.23× | 2.16× |
| Degree 131 sparse multiplication | 12.62× | 8.01× |
| Degree 131 dense multiplication | 5.44× | 4.22× |

`benchmark.py` used 64 seeded operand pairs per case, 9 alternating paired
rounds, and 8 repeats per round. Ratios above use the separately recorded
median times from each side; raw JSON retains all case measurements.

| Degree 131 curve operation | Paired run A | Paired run B |
| --- | ---: | ---: |
| `pointFromX` | 1.66× | 1.20× |
| `add` | 1.62× | 1.51× |
| `dbl` | 1.90× | 1.96× |
| `mul(P, 17)` | 2.94× | 1.71× |
| Unchanged `Onb.frob` control, isolated | 1.014× | 1.023× |

The curve-operation ratios are medians of 11 **matched old/new round ratios**
from `point_ops.py`. Each side used the same 48 seeded abscissae, the same
Euclid inverse and trace, and the same curve source. The unchanged Frobenius
control in one of those runs measured 0.864× amid scheduler spikes; a frozen
21-round isolated control measured 1.014× and 1.023× with exact outputs.
Earlier short-round variants and the outlier are retained. All point outputs
matched exactly.

`verify.py` matched **3,087** original multiplication outputs: exhaustive
degree-5 coordinate pairs, random degree-9/131 coordinate pairs, raw
noncanonical bit patterns, high bits, negative left operands, zero, and one.
`Onb.selfTest` passed for degrees 5, 9, and 131. Five local IC tests that do
not need CryptoMiniSat also passed with the candidate field loaded first.
The exact-output comparison passed under Python 3.9 and 3.13, and the same
14 Python 3.9 artifact replay tests used in CI passed locally.

The first window-only candidate improved wide dense products but regressed
degree-5/9 controls and one sparse control. The first density-aware candidate
used `int.bit_count`, which Python 3.9 lacks. A direct `popcount` fallback then
missed one wide random gate; the accepted version binds the available bit-count
implementation once and clears the frozen field gates. These are local Apple Silicon CPU
arithmetic-stage timings; this Python ONB path does not call Metal. A complete
index-calculus or DLP speedup is **unknown** because the local SAT solver
dependency is missing and there is no calibrated common operation unit or
verified recovered-log comparison for this change.
