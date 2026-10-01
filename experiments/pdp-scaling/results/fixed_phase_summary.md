# Matched PDP stage results

CPU seconds include setup and all PDP attempts. Ratios are candidate/baseline;
lower is cheaper. A dash means unmatched completions. No DLP/rho ratio is measured.

| n,l | phases | encoding / mode / guess | decided / targets | verified | CPU s | CPU / ANF baseline | gate |
|---|---|---|---:|---:|---:|---:|---|
| 7,4 | (0, 0, 0) | anf-s4 / cold / 0 | 16/16 | 2 | 4.7747 | 1.000 | baseline |
| 7,4 | (0, 0, 0) | s3-chain / cold / 0 | 16/16 | 2 | 1.9492 | 0.408 | pass (stage only) |
| 7,4 | (0, 0, 0) | s3-chain / incremental / 0 | 16/16 | 2 | 1.2220 | 0.256 | pass (stage only) |
| 7,4 | (0, 0, 0) | s3-chain / incremental / 2 | 16/16 | 2 | 1.1901 | 0.249 | pass (stage only) |
| 7,4 | (0, 0, 0) | s3-chain / template / 0 | 16/16 | 2 | 1.8270 | 0.383 | pass (stage only) |
| 7,4 | (0, 0, 0) | s4 / cold / 0 | 16/16 | 2 | 9.3455 | 1.957 | fail |
| 7,4 | (0, 0, 0) | s4 / incremental / 0 | 16/16 | 2 | 7.6798 | 1.608 | fail |
| 7,4 | (0, 0, 0) | s4 / incremental / 2 | 16/16 | 2 | 6.4938 | 1.360 | fail |
| 7,4 | (0, 0, 0) | s4 / template / 0 | 16/16 | 2 | 9.2342 | 1.934 | fail |
| 7,4 | (0, 1, 2) | anf-s4 / cold / 0 | 16/16 | 4 | 4.6579 | 1.000 | baseline |
| 7,4 | (0, 1, 2) | s3-chain / cold / 0 | 16/16 | 4 | 2.0976 | 0.450 | pass (stage only) |
| 7,4 | (0, 1, 2) | s3-chain / incremental / 0 | 16/16 | 4 | 1.6690 | 0.358 | pass (stage only) |
| 7,4 | (0, 1, 2) | s3-chain / incremental / 2 | 16/16 | 4 | 1.5740 | 0.338 | pass (stage only) |
| 7,4 | (0, 1, 2) | s3-chain / template / 0 | 16/16 | 4 | 2.0986 | 0.451 | pass (stage only) |
| 7,4 | (0, 1, 2) | s4 / cold / 0 | 16/16 | 4 | 8.1812 | 1.756 | fail |
| 7,4 | (0, 1, 2) | s4 / incremental / 0 | 16/16 | 4 | 7.6167 | 1.635 | fail |
| 7,4 | (0, 1, 2) | s4 / incremental / 2 | 16/16 | 4 | 5.3191 | 1.142 | fail |
| 7,4 | (0, 1, 2) | s4 / template / 0 | 16/16 | 4 | 8.7706 | 1.883 | fail |
| 13,6 | (0, 0, 0) | anf-s4 / cold / 0 | 0/8 | 0 | 9.6270 | — | baseline |
| 13,6 | (0, 0, 0) | s3-chain / cold / 0 | 0/8 | 0 | 8.1414 | — | fail |
| 13,6 | (0, 0, 0) | s3-chain / incremental / 0 | 0/8 | 0 | 8.1254 | — | fail |
| 13,6 | (0, 0, 0) | s3-chain / incremental / 2 | 0/8 | 0 | 8.0838 | — | fail |
| 13,6 | (0, 0, 0) | s3-chain / template / 0 | 0/8 | 0 | 8.0572 | — | fail |
| 13,6 | (0, 0, 0) | s4 / cold / 0 | 0/8 | 0 | 8.2709 | — | fail |
| 13,6 | (0, 0, 0) | s4 / incremental / 0 | 0/8 | 0 | 8.1891 | — | fail |
| 13,6 | (0, 0, 0) | s4 / incremental / 2 | 0/8 | 0 | 8.1760 | — | fail |
| 13,6 | (0, 0, 0) | s4 / template / 0 | 0/8 | 0 | 8.1484 | — | fail |
| 13,6 | (0, 1, 2) | anf-s4 / cold / 0 | 0/8 | 0 | 10.8009 | — | baseline |
| 13,6 | (0, 1, 2) | s3-chain / cold / 0 | 0/8 | 0 | 8.0948 | — | fail |
| 13,6 | (0, 1, 2) | s3-chain / incremental / 0 | 0/8 | 0 | 8.0927 | — | fail |
| 13,6 | (0, 1, 2) | s3-chain / incremental / 2 | 0/8 | 0 | 8.0653 | — | fail |
| 13,6 | (0, 1, 2) | s3-chain / template / 0 | 0/8 | 0 | 8.0564 | — | fail |
| 13,6 | (0, 1, 2) | s4 / cold / 0 | 0/8 | 0 | 8.2221 | — | fail |
| 13,6 | (0, 1, 2) | s4 / incremental / 0 | 0/8 | 0 | 8.1467 | — | fail |
| 13,6 | (0, 1, 2) | s4 / incremental / 2 | 0/8 | 0 | 8.1788 | — | fail |
| 13,6 | (0, 1, 2) | s4 / template / 0 | 0/8 | 0 | 8.0850 | — | fail |
