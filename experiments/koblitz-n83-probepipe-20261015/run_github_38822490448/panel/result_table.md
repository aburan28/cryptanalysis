| Statistic | Estimate [95%] | Reading |
| --- | --- | --- |
| Primary R_m: combined / combined+pipeline, ratio of means | 1.4001 [1.3971, 1.4032] (n=384) | improvement |
| R_g: ratio of geometric means (reported) | 1.4002 [1.3974, 1.4030] (n=384) | improvement |
| R_m, slice bootstrap (sensitivity) | 1.4001 [1.3850, 1.4170] (n=6) |  |
| Probes: combined / pipeline (must be 1) | 1.0000 [1.0000, 1.0000] (n=384) |  |
| A/A: pipeline / pipeline | 0.9961 [0.9944, 0.9978] (n=384) | pass |
| Planted: pipeline+full scan / pipeline | 2.0106 [2.0036, 2.0172] (n=384) | pass |
| Tuned rho / pipeline (means) | 6.8396 [6.1494, 7.6526] (n=384) |  |
| Tuned rho / pipeline (geomeans) | 9.3651 [8.1982, 10.6940] (n=384) |  |
| Tuned rho / combined (means) | 4.8852 [4.3824, 5.4682] (n=384) |  |
| Old 16 fresh combined / pipeline (means, secondary) | 1.3936 [1.3914, 1.3961] (n=16) |  |

- primary pC: online mean 525.8 ms, geomean 323.6 ms, 302.1 ns/probe; probes mean/law 1.007
- primary pP: online mean 375.5 ms, geomean 231.1 ms, 215.8 ns/probe; probes mean/law 1.007
- primary pPaa: online mean 377.0 ms, geomean 231.9 ms, 216.6 ns/probe; probes mean/law 1.007
- primary pX: online mean 755.1 ms, geomean 464.7 ms, 433.9 ns/probe; probes mean/law 1.007
- S_rho pC: 0.02062 (S_probe 0.01880)
- S_rho pP: 0.01473 (S_probe 0.01880)
- delta S_rho, pipeline minus combined: -0.00589

Primary verdict (ratio of means): **improvement**; ratchet: new n=83 one-target baseline: lift_scan + Feistel order + software-pipelined, prefetched root-table probes.
