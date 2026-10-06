## Measured end-to-end cost (baseline `IC1N19Ckb1fb26PDP2xlRCsampleLAgaussTDpdpISO0hc0cc43a2b0ee`, n19l5-prefix)

Every row is a complete IC pipeline with every target's log verified by scalar replay. `total` is the mean cold total over the workloads (3 targets each, rps); `speedup` is baseline_total / candidate_total per workload, geometric mean [min, max] over the paired workloads. `x rho` and `x floor` are the boundary ratios fixed in the workload records; `S` is total / sqrt(r) in rps.

| candidate | l | family | seed | role | verified | queries (mean) | predicted total | measured total | speedup vs baseline | x rho | x floor | S |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `IC1N19Ckb1fb26PDP2xlRCsampleLAgaussTDpdpISO0hc0cc43a2b0ee` | 5 | prefix | 1 | only | 3/3 | 41404 | 5.711e+11 | 8.488e+11 | 1.00 [1.00, 1.00] | 1.598e+04 | 9.782e+04 | 2.346e+09 |
| `IC1N19Ckb1fb40PDP2xlRCsampleLAgaussTDpdpISO0h7733e2629fce` | 5 | geometric | 10 | best | 3/3 | 11367 | 3.446e+11 | 2.346e+11 | 3.72 [2.94, 4.51] | 4417 | 2.704e+04 | 6.485e+08 |
| `IC1N19Ckb1fb38PDP2xlRCsampleLAgaussTDpdpISO0heeaa972ff40b` | 5 | geometric | 36 | median | 3/3 | 35337 | 8.263e+11 | 7.239e+11 | 1.26 [0.82, 1.77] | 1.363e+04 | 8.343e+04 | 2.001e+09 |
| `IC1N19Ckb1fb18PDP2xlRCsampleLAgaussTDpdpISO0h8c75fca556e3` | 5 | geometric | 26 | worst | 3/3 | 48412 | 1.674e+12 | 1.024e+12 | 0.85 [0.66, 1.15] | 1.927e+04 | 1.18e+05 | 2.83e+09 |
| `IC1N19Ckb1fb48PDP2xlRCsampleLAgaussTDpdpISO0h99000076d415` | 5 | geomtraceu | 10 | best | 3/3 | 10059 | 2.338e+11 | 2.075e+11 | 4.35 [2.93, 5.81] | 3907 | 2.392e+04 | 5.736e+08 |
| `IC1N19Ckb1fb34PDP2xlRCsampleLAgaussTDpdpISO0h7ac948ea649a` | 5 | geomtraceu | 46 | median | 3/3 | 20029 | 3.583e+11 | 4.113e+11 | 2.14 [1.61, 2.57] | 7743 | 4.74e+04 | 1.137e+09 |
| `IC1N19Ckb1fb30PDP2xlRCsampleLAgaussTDpdpISO0hd40d5825cb02` | 5 | geomtraceu | 34 | worst | 3/3 | 25879 | 5.698e+11 | 5.318e+11 | 1.65 [1.21, 2.62] | 1.001e+04 | 6.129e+04 | 1.47e+09 |
| `IC1N19Ckb1fb40PDP2xlRCsampleLAgaussTDpdpISO0h525599ac6842` | 5 | kertrace | 25 | best | 3/3 | 10381 | 2.715e+11 | 2.150e+11 | 4.10 [2.90, 5.80] | 4048 | 2.478e+04 | 5.943e+08 |
| `IC1N19Ckb1fb28PDP2xlRCsampleLAgaussTDpdpISO0h4ef2f2514d12` | 5 | kertrace | 17 | median | 3/3 | 19626 | 3.716e+11 | 4.042e+11 | 2.46 [1.09, 3.78] | 7609 | 4.658e+04 | 1.117e+09 |
| `IC1N19Ckb1fb20PDP2xlRCsampleLAgaussTDpdpISO0h0d6ff78cc84a` | 5 | kertrace | 13 | worst | 3/3 | 24864 | 6.417e+11 | 5.235e+11 | 1.85 [1.01, 4.25] | 9855 | 6.033e+04 | 1.447e+09 |
| `IC1N19Ckb1fb36PDP2xlRCsampleLAgaussTDpdpISO0ha0d4ee088638` | 5 | random | 36 | best | 3/3 | 21082 | 4.601e+11 | 4.366e+11 | 1.97 [1.71, 2.15] | 8219 | 5.031e+04 | 1.207e+09 |
| `IC1N19Ckb1fb28PDP2xlRCsampleLAgaussTDpdpISO0h282888856286` | 5 | random | 44 | median | 3/3 | 44417 | 8.154e+11 | 9.199e+11 | 0.95 [0.73, 1.12] | 1.732e+04 | 1.06e+05 | 2.543e+09 |
| `IC1N19Ckb1fb20PDP2xlRCsampleLAgaussTDpdpISO0h4d1148bf5839` | 5 | random | 13 | worst | 3/3 | 73770 | 1.741e+12 | 1.512e+12 | 0.57 [0.43, 0.74] | 2.847e+04 | 1.743e+05 | 4.18e+09 |
| `IC1N19Ckb1fb62PDP2xlRCsampleLAgaussTDpdpISO0h0b6a6c6cebbd` | 6 | prefix | 1 | only | 3/3 | 27051 | 8.343e+11 | 7.411e+11 | 1.20 [0.86, 1.58] | 1.395e+04 | 8.541e+04 | 2.049e+09 |
| `IC1N19Ckb1fb78PDP2xlRCsampleLAgaussTDpdpISO0h351a0b6bccf0` | 6 | geometric | 12 | best | 3/3 | 13022 | 4.111e+11 | 3.574e+11 | 2.46 [2.02, 3.42] | 6729 | 4.119e+04 | 9.879e+08 |
| `IC1N19Ckb1fb62PDP2xlRCsampleLAgaussTDpdpISO0h20afdeb9e970` | 6 | geometric | 42 | median | 3/3 | 18874 | 5.396e+11 | 5.209e+11 | 1.64 [1.45, 1.92] | 9807 | 6.003e+04 | 1.44e+09 |
| `IC1N19Ckb1fb48PDP2xlRCsampleLAgaussTDpdpISO0h6070f794a5f2` | 6 | geometric | 6 | worst | 3/3 | 37215 | 8.297e+11 | 1.017e+12 | 1.10 [0.44, 1.89] | 1.915e+04 | 1.172e+05 | 2.811e+09 |
| `IC1N19Ckb1fb78PDP2xlRCsampleLAgaussTDpdpISO0h025a8b000651` | 6 | geomtraceu | 4 | best | 3/3 | 7465 | 1.997e+11 | 2.058e+11 | 4.21 [2.99, 5.37] | 3874 | 2.371e+04 | 5.687e+08 |
| `IC1N19Ckb1fb62PDP2xlRCsampleLAgaussTDpdpISO0hb0c0716f6e86` | 6 | geomtraceu | 30 | median | 3/3 | 8495 | 2.520e+11 | 2.351e+11 | 3.71 [2.97, 4.60] | 4426 | 2.71e+04 | 6.499e+08 |
| `IC1N19Ckb1fb54PDP2xlRCsampleLAgaussTDpdpISO0he1784727f725` | 6 | geomtraceu | 11 | worst | 3/3 | 10452 | 3.269e+11 | 2.922e+11 | 3.10 [1.81, 4.19] | 5501 | 3.367e+04 | 8.077e+08 |
| `IC1N19Ckb1fb76PDP2xlRCsampleLAgaussTDpdpISO0ha4c5bca5a133` | 6 | kertrace | 31 | best | 3/3 | 9220 | 2.419e+11 | 2.911e+11 | 2.91 [2.75, 3.01] | 5481 | 3.355e+04 | 8.048e+08 |
| `IC1N19Ckb1fb64PDP2xlRCsampleLAgaussTDpdpISO0hcb6d9ecaca72` | 6 | kertrace | 30 | median | 3/3 | 8535 | 2.755e+11 | 2.664e+11 | 3.20 [2.63, 3.65] | 5015 | 3.07e+04 | 7.363e+08 |
| `IC1N19Ckb1fb58PDP2xlRCsampleLAgaussTDpdpISO0hd1c539dd6144` | 6 | kertrace | 37 | worst | 3/3 | 14098 | 3.441e+11 | 4.380e+11 | 2.02 [1.34, 3.24] | 8247 | 5.048e+04 | 1.211e+09 |
| `IC1N19Ckb1fb66PDP2xlRCsampleLAgaussTDpdpISO0h64e3bfe79d60` | 6 | random | 29 | best | 3/3 | 10145 | 2.572e+11 | 3.178e+11 | 2.69 [2.15, 3.28] | 5983 | 3.662e+04 | 8.784e+08 |
| `IC1N19Ckb1fb60PDP2xlRCsampleLAgaussTDpdpISO0ha631ab2b7105` | 6 | random | 17 | median | 3/3 | 29958 | 6.163e+11 | 9.404e+11 | 0.91 [0.82, 1.02] | 1.771e+04 | 1.084e+05 | 2.6e+09 |
| `IC1N19Ckb1fb46PDP2xlRCsampleLAgaussTDpdpISO0hf22e0769b66a` | 6 | random | 28 | worst | 3/3 | 76487 | 1.986e+12 | 2.334e+12 | 0.45 [0.22, 1.05] | 4.395e+04 | 2.69e+05 | 6.452e+09 |
| `IC1N19Ckb1fb136PDP2xlRCsampleLAgaussTDpdpISO0h249c2b4b8d9c` | 7 | prefix | 1 | only | 3/3 | 8471 | 3.878e+11 | 3.446e+11 | 2.47 [2.12, 2.75] | 6487 | 3.971e+04 | 9.524e+08 |
| `IC1N19Ckb1fb152PDP2xlRCsampleLAgaussTDpdpISO0h63941627eb1e` | 7 | geometric | 11 | best | 3/3 | 9085 | 3.317e+11 | 3.796e+11 | 2.27 [1.91, 2.64] | 7147 | 4.375e+04 | 1.049e+09 |
| `IC1N19Ckb1fb136PDP2xlRCsampleLAgaussTDpdpISO0h9981681ce8d5` | 7 | geometric | 35 | median | 3/3 | 10088 | 4.046e+11 | 4.093e+11 | 2.08 [1.79, 2.67] | 7706 | 4.717e+04 | 1.131e+09 |
| `IC1N19Ckb1fb112PDP2xlRCsampleLAgaussTDpdpISO0h0a7d8a6f3394` | 7 | geometric | 34 | worst | 3/3 | 16396 | 5.517e+11 | 6.393e+11 | 1.52 [0.71, 2.46] | 1.204e+04 | 7.368e+04 | 1.767e+09 |
| `IC1N19Ckb1fb130PDP2xlRCsampleLAgaussTDpdpISO0hb34aa06f6d50` | 7 | geomtraceu | 3 | best | 3/3 | 6205 | 1.967e+11 | 2.955e+11 | 2.89 [2.38, 3.28] | 5562 | 3.405e+04 | 8.167e+08 |
| `IC1N19Ckb1fb108PDP2xlRCsampleLAgaussTDpdpISO0h990cb5d5d404` | 7 | geomtraceu | 37 | median | 3/3 | 7093 | 2.326e+11 | 3.242e+11 | 2.66 [1.95, 3.27] | 6104 | 3.737e+04 | 8.962e+08 |
| `IC1N19Ckb1fb138PDP2xlRCsampleLAgaussTDpdpISO0h2e843e1ec086` | 7 | geomtraceu | 9 | worst | 3/3 | 5227 | 2.797e+11 | 2.637e+11 | 3.24 [2.63, 3.63] | 4965 | 3.039e+04 | 7.29e+08 |
| `IC1N19Ckb1fb142PDP2xlRCsampleLAgaussTDpdpISO0h76cb647a55ba` | 7 | kertrace | 22 | best | 3/3 | 4164 | 3.329e+11 | 3.285e+11 | 2.61 [2.02, 3.28] | 6184 | 3.785e+04 | 9.079e+08 |
| `IC1N19Ckb1fb138PDP2xlRCsampleLAgaussTDpdpISO0h0ea4b887b395` | 7 | kertrace | 21 | median | 3/3 | 3988 | 3.884e+11 | 3.153e+11 | 2.71 [2.47, 3.07] | 5936 | 3.634e+04 | 8.716e+08 |
| `IC1N19Ckb1fb124PDP2xlRCsampleLAgaussTDpdpISO0h818dfcb8a4c3` | 7 | kertrace | 15 | worst | 3/3 | 8295 | 5.381e+11 | 6.519e+11 | 1.40 [0.97, 2.21] | 1.227e+04 | 7.513e+04 | 1.802e+09 |
| `IC1N19Ckb1fb116PDP2xlRCsampleLAgaussTDpdpISO0h8b98a8b480fb` | 7 | random | 47 | best | 3/3 | 5927 | 3.905e+11 | 4.425e+11 | 2.11 [1.11, 3.49] | 8332 | 5.1e+04 | 1.223e+09 |
| `IC1N19Ckb1fb124PDP2xlRCsampleLAgaussTDpdpISO0h33bfd876a487` | 7 | random | 8 | median | 3/3 | 10539 | 7.943e+11 | 8.023e+11 | 1.07 [0.83, 1.31] | 1.511e+04 | 9.247e+04 | 2.218e+09 |
| `IC1N19Ckb1fb118PDP2xlRCsampleLAgaussTDpdpISO0hdbd2249cf263` | 7 | random | 41 | worst | 3/3 | 17086 | 1.044e+12 | 1.309e+12 | 0.67 [0.48, 0.89] | 2.465e+04 | 1.509e+05 | 3.62e+09 |
