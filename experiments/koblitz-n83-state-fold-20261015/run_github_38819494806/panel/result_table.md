# n=83 state fold: frozen result

Verdict: **improvement**

| statistic | estimate [95%] |
| --- | --- |
| primary_cold_cB_over_cF | 1.8372 [1.8216, 1.8528] (n=16) |
| aa_cold_cF_over_cFaa | 1.0012 [0.9996, 1.0029] (n=16) |
| planted_cold_cX_over_cF | 1.7175 [1.7081, 1.7256] (n=16) |
| planted_cold_cB_over_cX | 1.0697 [1.0647, 1.0757] (n=16) |
| setup_cB_over_cF | 1.8568 [1.8486, 1.8669] (n=16) |
| online_cB_over_cF | 0.9490 [0.9405, 0.9548] (n=16) |
| online_cB_over_cF_geometric | 0.9539 [0.9455, 0.9630] (n=16) |
| index_build_cB_over_cF | 1.9554 [1.9463, 1.9666] (n=16) |
| peak_rss_cB_over_cF | 1.9715 [1.9714, 1.9717] (n=16) |
| cold_cBL_over_cFL | 1.8324 [1.8038, 1.8542] (n=16) |
| cold_cBF_over_cFF | 1.8277 [1.8093, 1.8447] (n=16) |
| cold_better_single_over_cF | 1.8420 [1.8073, 1.8759] (n=16) |
| cold_cF_over_cFI | 1.3307 [1.3250, 1.3357] (n=16) |
| cold_gap_cB_over_rT | 12.7687 [10.1256, 16.5895] (n=16) |
| cold_gap_cF_over_rT | 6.9501 [5.5342, 9.0140] (n=16) |
| online_gap_rT_over_cB | 6.4521 [4.3774, 11.7019] (n=16) |
| online_gap_rT_over_cF | 6.1232 [4.1522, 11.0853] (n=16) |

Means (ms): {"cB": 41953.4, "cF": 22835.6, "cFaa": 22808.8, "cX": 39220.3, "cBF": 42226.7, "cFF": 23103.3, "cFI": 17160.5, "cBL": 42062.5, "cFL": 22955.1}

Cold S (setup + online): {"cB": 1.6195998330463968, "cF": 0.8815640321747729, "cFI": 0.6624760307258664}

Rank stage: {"per_attempt_cost_kB_over_kN": {"estimate": 2.245105439782327, "ci95": [2.0517132897154418, 2.4650327823530214], "attempts": [1200, 1200], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}, "rank_stage_kB_over_kN": 2.244721761182587, "S_cold_ledger_rank_plus_setup_plus_online": {"old_rank_kB_plus_cB": 30.85514872125677, "fold_only_rank_kB_plus_cF": 30.117112920385146, "fold_and_rank_kN_plus_cF": 13.905694413843193}, "cold_gap_incl_rank_over_rT": {"old_rank_kB_plus_cB": 243.25806912039397, "fold_only_rank_kB_plus_cF": 237.4394887115408, "fold_and_rank_kN_plus_cF": 109.63072657495727}}

Checks: {"all_executed_rows_valid": true, "one_scalar_per_point_ic_and_rho": true, "oracle_replay": true, "one_relation_per_order_group": true, "probe_identities": true, "rank_tables_equal_archived": true, "receipt_matches_schedule": true, "every_scheduled_row_present": true, "all_points_complete": true}

Controls: {"aa_inside_0.97_1.03": true, "planted_lower_bound_above_1": true}
