# Q1518: phase-three mask reduces N83 calls per usable first pair by 0.89 bits

Sweeping all nine frozen Q1488 leaf-polarity masks with Q1517's in-process
eight-pair enumerator found **phase 3** to have the lowest counted work per
exact-base-usable first pair on both ordinary N83 public points. It produced
five usable pairs among eight for **195,862 CNF+XOR calls** on the selected
point and **198,186** on the holdout. The prior phase-two setting produced
three usable pairs for 218,096 and 220,420 calls. Calls per usable pair fell
by **1.856× (0.892 bits)** and **1.854× (0.890 bits)**, respectively.

| Frozen mask phase | Flipped leaf variables | Usable pairs / 8, both points | Selected calls to eight pairs | Holdout calls to eight pairs |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 75,372 | 77,696 |
| 1 | 169 | 0 | 224,892 | 227,216 |
| 2 | 171 | 3 | 218,096 | 220,420 |
| **3** | **163** | **5** | **195,862** | **198,186** |
| 4 | 152 | 5 | 215,714 | 218,038 |
| 5 | 181 | 0 | 214,202 | 216,526 |
| 6 | 162 | 2 | 210,512 | 212,836 |
| 7 | 160 | 0 | 222,134 | 224,458 |
| 8 | 168 | 0 | 206,360 | 208,684 |

All **18 ordinary-query cells** reached eight distinct first-pair markers
within the frozen 10-second CPU and 15-second wall caps. The exact curve is
`EC1N83Ckb1h876c2921cb64`; the W≤5 factor base has **B=30,977,592**
subgroup-usable points, **K=186,612** signed-Frobenius columns, and base
digest `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The selected and holdout workload IDs are `2eb250a29072` and
`394256b9f901`. The two targets produced identical first-pair bit sequences
at every mask phase, so these are matched workload replications, not
independent samples of usable-pair probability. CPU wall values are
exploratory without an isolation receipt. Phase-three peak child RSS was
912,359,424 B and 912,982,016 B, respectively.

## Ordinary complementary-pair screen

The five phase-three usable pairs per point imply **40 signed complements**.
Q1512's exact 32 MiB raw-x Bloom scanner was launched against the complete
N83 W≤5 base with a 30-second cap per complement. The run was interrupted
after 16 attempts when host contention slowed the native scanner: **14
completed with zero exact-base hits**, **two timed out**, and **24 have no
receipt**. The completed scans charged **1,084,215,720 = 2^30.014 batch
field multiplications**, excluding inversion internals; the two timeouts
also consumed resources but have no complete operation count. Thus the
ordinary relation yield for this phase-three set is **censored**, and no
rank cost or complete N83 decomposition cost follows from it.

The [scan protocol](scan_protocol.json), [terminal partial record](scan_result.json),
[partial stream](scan_result.partial.json), and per-cell outputs under
[scans](scans) retain the exact attempted, timed-out, interrupted, and
unattempted cells. `salvage_scan.py` freezes the interrupted process's
16 completed or capped receipts without assigning zero work or yield to
missing cells. The interruption was a measurement-host condition; it is not
a mathematical rejection of the remaining complements.

This is a `Q1518` `PDP4sat`/`PDP4hybrid` stage study with `isogeny: "none"`
and null candidate/run IDs. It improves first-pair production, but the
N131 W≤6 complete-scan transfer remains `2^35.933` batch multiplications
per usable first pair, and the Q1506 independent-first-pair rank-supply
model remains `2^123.289` in that scanner unit. A fully charged N131 solve
exponent remains unknown. Completing the censored phase-three scans in a
verified resource envelope and replacing full scans with a
target-conditioned second-pair lookup are the next direct gates.

The [protocol](protocol.json), [result](result.json), [accounting](analysis.json),
and [validator](validate.py) bind the inputs, source/binary identities,
individual counters, exact-base replays, scan statuses, and resource limits.
Recheck with:

```sh
env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_q1518_inprocess_mask_sweep/validate.py
```
