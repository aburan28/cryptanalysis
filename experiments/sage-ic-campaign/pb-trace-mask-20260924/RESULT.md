# Result: polynomial-basis trace mask

All 16 frozen cells matched exact outputs. Ratios are paired median
incumbent/candidate operation times. Each point batch recovers 64 candidate
points from x coordinates and checks the complete returned results.

| Complete measured operation | Primary range | Independent confirmation range |
| --- | ---: | ---: |
| 64 `pointFromX` calls, warm | 1.72–2.97x | 1.73–2.57x |
| First `pointFromX` call, mask included | 1.36–13.00x | 1.42–12.12x |

The 256-trace stage diagnostic improved 71–6,616x in the primary run and
72–5,895x in confirmation. The containing point-recovery gain is the useful
boundary for this change. No complete IC pipeline or recovered-DLP speedup
was measured.
