| Statistic | Estimate [95%] | Reading |
| --- | --- | --- |
| Fresh primary (section 23): left-major / feistel, online | 3.4287 [1.0090, 7.4215] (n=16) | improvement |
| Fresh: ratio of geometric means, online | 1.5010 [0.5970, 3.6151] (n=16) |  |
| Fresh: median per-point ratio, online | 1.7315 [0.4717, 5.8080] (n=16) |  |
| Fresh: section 23, probes | 3.4012 [0.9411, 7.4777] (n=16) |  |
| Fresh A/A: left-major / left-major | 1.0017 [0.9917, 1.0148] (n=16) | pass |
| Fresh planted: left-major / planted half-skip | 2.0008 [1.9658, 2.0269] (n=16) | pass |
| Q0: left-major / feistel (median of blocks) | 4.3257 [4.2837, 4.4547] (n=8) | improvement |
| Q0 A/A | 0.9967 [0.9886, 1.0088] (n=8) | pass |
| Q0 planted | 1.9893 [1.9469, 2.0565] (n=8) | pass |
| Held-out 384 (section 23): left-major / feistel, online | 1.4507 [1.2023, 1.7424] (n=384) | improvement |
| Held-out: ratio of geometric means, online | 1.2728 [1.0636, 1.5278] (n=384) |  |
| Held-out: section 23, probes | 1.4760 [1.2321, 1.7651] (n=384) |  |
| Tuned rho / IC left-major, Q0 | 0.5561 [0.3295, 0.9481] (n=8) |  |
| Tuned rho / IC feistel, Q0 | 2.4799 [1.4043, 3.6850] (n=8) |  |
| Tuned rho / IC left-major, fresh (section 23) | 1.0024 [0.4838, 3.3930] (n=16) |  |
| Tuned rho / IC feistel, fresh (section 23) | 3.4370 [2.0774, 6.1418] (n=16) |  |
| Tuned rho / IC left-major, fresh (geometric means) | 2.7902 [1.0964, 6.3472] (n=16) |  |
| Tuned rho / IC feistel, fresh (geometric means) | 4.1882 [2.3122, 7.4010] (n=16) |  |

- fresh fB: probes mean/law 2.303 [0.656, 4.209], CV 1.62, geomean probes 1142075; online geomean 417.4 ms
- fresh fP: probes mean/law 0.677 [0.407, 1.003], CV 0.93, geomean probes 759062; online geomean 278.1 ms
- fresh fBaa: probes mean/law 2.303 [0.642, 4.165], CV 1.62, geomean probes 1142075; online geomean 414.7 ms
- fresh fH: probes mean/law 1.152 [0.337, 2.105], CV 1.62, geomean probes 571561; online geomean 209.4 ms
- held-out hB: probes mean/law 1.428 [1.234, 1.638], CV 1.42, geomean probes 1178423; online geomean 426.2 ms
- held-out hP: probes mean/law 0.967 [0.863, 1.074], CV 1.08, geomean probes 907420; online geomean 334.9 ms

Primary verdict (16 fresh points): **improvement**; held-out secondary: **improvement**; Q0 secondary: improvement; ratchet: new one-target baseline: the feistel scan order (B's pipeline otherwise unchanged).
