| Statistic | Estimate [95%] | Reading |
| --- | --- | --- |
| Primary R_m: better single / combined, ratio of means | 1.2363 [1.0671, 1.4276] (n=576) | not_separated |
| Primary R_g: better single / combined, ratio of geometric means | 1.0611 [0.9083, 1.2430] (n=576) |  |
| Primary R_m, slice bootstrap (sensitivity) | 1.2363 [1.1005, 1.3957] (n=9) |  |
| Combined vs lift_scan only (means) | 1.2363 [1.0733, 1.4307] (n=576) |  |
| Combined vs lift_scan only (geomeans) | 1.0611 [0.9055, 1.2435] (n=576) |  |
| Combined vs Feistel only (means) | 1.5994 [1.5965, 1.6023] (n=576) |  |
| Combined vs Feistel only (geomeans) | 1.5985 [1.5962, 1.6009] (n=576) |  |
| Combined vs B (means) | 1.9992 [1.7285, 2.3090] (n=576) | improvement |
| Combined vs B (geomeans) | 1.7143 [1.4646, 2.0080] (n=576) |  |
| lift_scan only vs B (means) | 1.6171 [1.6156, 1.6186] (n=576) |  |
| Feistel only vs B (means) | 1.2500 [1.0825, 1.4408] (n=576) |  |
| Probes: B / Feistel (means) | 1.2523 [1.0877, 1.4430] (n=576) |  |
| A/A: combined / combined | 1.0081 [1.0058, 1.0104] (n=576) | pass |
| Planted: lift+full / combined | 1.7290 [1.7256, 1.7321] (n=576) | pass |
| Tuned rho / combined (means) | 4.6628 [4.2501, 5.1308] (n=576) |  |
| Tuned rho / combined (geomeans) | 7.2786 [6.5115, 8.1684] (n=576) |  |
| Tuned rho / B (means) | 2.3323 [2.0713, 2.6339] (n=576) |  |
| Old 384 held-out R_m (secondary) | 1.4710 [1.2283, 1.6213] (n=384) | improvement |
| Old 384 held-out R_g (secondary) | 1.2942 [1.0757, 1.5564] (n=384) |  |
| Old 384 held-out combined vs B (means) | 2.3876 [1.9776, 2.8539] (n=384) |  |
| Old 16 fresh R_m (secondary) | 1.6237 [0.9876, 1.6270] (n=16) |  |
| Old 16 fresh combined vs B (means) | 5.5007 [1.6284, 11.9937] (n=16) |  |

- better single arm (point estimate): means pL, geomeans pL
- primary pB: online mean 1072.8 ms, geomean 496.1 ms; probes mean/law 1.256, CV 1.41
- primary pL: online mean 663.4 ms, geomean 307.0 ms; probes mean/law 1.256, CV 1.41
- primary pF: online mean 858.3 ms, geomean 462.6 ms; probes mean/law 1.003, CV 1.05
- primary pLF: online mean 536.6 ms, geomean 289.4 ms; probes mean/law 1.003, CV 1.05
- primary pLFaa: online mean 532.3 ms, geomean 286.9 ms; probes mean/law 1.003, CV 1.05
- primary pX: online mean 927.8 ms, geomean 499.8 ms; probes mean/law 1.003, CV 1.05
- S_rho pB: 0.04137 (S_probe 0.02344)
- S_rho pL: 0.02558 (S_probe 0.02344)
- S_rho pF: 0.03310 (S_probe 0.01872)
- S_rho pLF: 0.02069 (S_probe 0.01872)
- delta S_rho, combined minus better single (pL): -0.00489; combined minus B: -0.02068

Primary verdict (both bounds): **not_separated**; combined vs B: improvement; old held-out secondary: improvement; ratchet: no new baseline.
