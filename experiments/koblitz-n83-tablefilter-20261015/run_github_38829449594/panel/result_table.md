| Statistic | Estimate [95%] | Reading |
| --- | --- | --- |
| Primary R_m: pipeline / pipeline + filter table, ratio of means | 1.0633 [1.0589, 1.0679] (n=384) | improvement |
| R_g: ratio of geometric means (reported) | 1.0611 [1.0579, 1.0644] (n=384) | improvement |
| R_m, slice bootstrap (sensitivity) | 1.0633 [1.0428, 1.0882] (n=6) |  |
| Probes: pipeline / filter table (must be 1) | 1.0000 [1.0000, 1.0000] (n=384) |  |
| A/A: filter table / filter table | 1.0011 [0.9999, 1.0022] (n=384) | pass |
| Planted: filter + discarded table lookups / filter | 1.0545 [1.0529, 1.0565] (n=384) | pass |
| Cold (setup + online): pipeline / filter table | 1.0101 [1.0090, 1.0113] (n=384) |  |
| Secondary: pipeline / compact slots only | 1.0581 [1.0536, 1.0627] (n=384) |  |
| Secondary: compact only / filter table | 1.0049 [1.0035, 1.0066] (n=384) |  |
| Secondary: 32 MiB filter / 64 MiB filter | 1.0029 [1.0019, 1.0039] (n=384) |  |
| Tuned rho / filter table (means) | 6.5642 [5.8533, 7.3649] (n=384) |  |
| Tuned rho / filter table (geomeans) | 9.9310 [8.6688, 11.3811] (n=384) |  |
| Tuned rho / pipeline (means) | 6.1734 [5.5050, 6.9319] (n=384) |  |
| Old 16 fresh pipeline / filter table (means, secondary) | 1.0573 [1.0509, 1.0633] (n=16) |  |

- primary pP: online mean 473.0 ms, geomean 265.2 ms, 253.8 ns/probe; probes mean/law 1.079; setup 51081 ms, peak RSS 5.41 GiB
- primary pT: online mean 444.8 ms, geomean 249.9 ms, 238.7 ns/probe; probes mean/law 1.079; filter false positives 0.0244 of probes; setup 50593 ms, peak RSS 3.45 GiB
- primary pTaa: online mean 444.4 ms, geomean 249.7 ms, 238.4 ns/probe; probes mean/law 1.079; filter false positives 0.0244 of probes; setup 50508 ms, peak RSS 3.45 GiB
- primary pX: online mean 469.1 ms, geomean 263.3 ms, 251.7 ns/probe; probes mean/law 1.079; filter false positives 0.0244 of probes; setup 50480 ms, peak RSS 3.45 GiB
- primary pK: online mean 447.0 ms, geomean 251.0 ms, 239.8 ns/probe; probes mean/law 1.079; setup 49288 ms, peak RSS 3.41 GiB
- primary pT29: online mean 443.5 ms, geomean 249.2 ms, 238.0 ns/probe; probes mean/law 1.079; filter false positives 0.0030 of probes; setup 50705 ms, peak RSS 3.48 GiB
- setup pipeline / filter table: 1.0097; peak RSS: 1.5714
- S_rho pP: 0.01605 (S_probe 0.02013; cold S_rho 1.74985)
- S_rho pT: 0.01510 (S_probe 0.02013; cold S_rho 1.73231)
- delta S_rho, filter table minus pipeline: -0.00096

Primary verdict (ratio of means): **improvement**; ratchet: new n=83 one-target baseline: lift_scan + Feistel order + prefetched probes + two-level root table (32 MiB blocked filter, 16-byte exact slots).
