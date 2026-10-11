# Native Sage point packing: local result

The accepted candidate changes only the input side of the NTL point codec.
Each paired timing cell compares it with the exact installed output codec
from PR #74 on the same public Koblitz inputs. Twelve balanced rounds per
cell use at least 131,072 point outputs per arm and round. Each warm call
includes packing, CPU or Metal table application, Sage-point reconstruction,
exact verification and cleanup. Plan setup is separately recorded.

| Phase | GF(2^m) | Points | Power | CPU gain | Metal gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Primary | 19 | 1,024 | 1 | 1.469× | 1.198× |
| Primary | 131 | 4,096 | 1 | 1.469× | 1.287× |
| Primary | 131 | 4,096 | 65 | 1.426× | 1.231× |
| Primary | 131 | 16,384 | 65 | 1.431× | 1.219× |
| Confirmation | 31 | 2,304 | 7 | 1.351× | 1.329× |
| Confirmation | 163 | 2,304 | 65 | 1.194× | 1.169× |

The primary geometric mean across eight CPU/Metal cells is **1.337×**;
the independent confirmation mean across four cells is **1.258×**.
The lowest individual cell is **1.169×**. All **37,773,312 timed outputs**
matched Sage's Frobenius isogeny result. Fresh-process peak RSS in the
4,096-point degree-131 CPU check fell from 279,117,824 to 276,185,088
bytes, a 2.80 MiB decrease. The frozen gate required both means above
1.05×, no cell below 0.98×, exact outputs, and RSS within 5% or 2 MiB;
this run passes those local criteria.

The original packing candidate in `run-002/` had a 1.142× primary and
1.071× confirmation geometric mean, but two cells measured 0.928× and
0.918×. It failed the no-regression gate and was revised before the fresh
`run-003/` measurement. The phase profile in `run-001/` found packing at
19–40% of complete call time in six CPU/Metal cells. The benchmark host
is shared, so the observed ratios are local and should be remeasured on
another machine.

The focused pack tests passed three groups, including iterators, infinity,
wrong-curve rejection, custom `xy()` hooks, and a deliberately
non-normalized standard point. The output codec contract tests passed two
groups; the installed CPU/Metal hardware suite passed six groups.
Source and binary identities are recorded in the receipts. No field map,
Metal shader, or point-addition change is included.

This result covers warm public point-map calls. It does not establish a
verified end-to-end index-calculus speedup.
