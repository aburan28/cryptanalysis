# n=83 stacked producer: frozen result

Verdict: **improvement**

| statistic | estimate [95%] |
| --- | --- |
| primary_e2e_cP_over_cS | 3.2391 [2.9809, 3.5240] (n=20) |
| aa_e2e_cS_over_cSaa | 0.9996 [0.9339, 1.0697] (n=20) |
| aa_cold_cS_over_cSaa | 0.9986 [0.9970, 0.9999] (n=20) |
| planted_cold_cSX_over_cS | 1.7351 [1.7293, 1.7404] (n=20) |
| online_cP_over_cS | 0.9562 [0.9524, 0.9608] (n=20) |
| online_cP_over_cS_geometric | 0.9580 [0.9533, 0.9622] (n=20) |
| cold_without_rank_cP_over_cS | 1.9019 [1.8937, 1.9096] (n=20) |
| setup_cP_over_cS | 1.9161 [1.9112, 1.9211] (n=20) |
| index_build_cP_over_cS | 2.0184 [2.0132, 2.0240] (n=20) |
| peak_rss_cP_over_cS | 3.1004 [3.1001, 3.1006] (n=20) |
| e2e_cSmF_over_cS | 1.0272 [0.9622, 1.0971] (n=20) |
| e2e_cSmS_over_cS | 1.0231 [0.9543, 1.0958] (n=20) |
| online_cSmF_over_cS | 0.9394 [0.9363, 0.9420] (n=20) |
| online_cSmS_over_cS | 1.0228 [1.0195, 1.0249] (n=20) |
| cold_without_rank_cSmF_over_cS | 1.8662 [1.8594, 1.8722] (n=20) |
| cold_without_rank_cSmS_over_cS | 1.0106 [1.0090, 1.0120] (n=20) |
| cold_without_rank_cS_over_cSF | 0.9673 [0.9658, 0.9687] (n=20) |
| online_cS_over_cSF | 1.0715 [1.0684, 1.0746] (n=20) |
| cold_without_rank_cS_over_cSI | 1.3308 [1.3270, 1.3342] (n=20) |
| e2e_cold_gap_cP_over_rT | 305.8238 [237.4977, 403.7772] (n=20) |
| e2e_cold_gap_cS_over_rT | 94.4168 [73.5188, 125.2922] (n=20) |
| online_gap_rT_over_cP | 7.5168 [4.4063, 13.5984] (n=20) |
| online_gap_rT_over_cS | 7.1879 [4.1981, 12.9440] (n=20) |

Mean cold without rank (ms): {"cP": 49372.8, "cSmF": 48447.2, "cS": 25960.4, "cSaa": 25997.9, "cSX": 45043.9, "cSmS": 26234.4, "cSF": 26839.0, "cSI": 19507.8}

S end-to-end cold: {"cP": 31.355763867020947, "cS": 9.680450084121011, "cSaa": 9.683927652523323, "cSmF": 9.943888437638819, "cSmS": 9.90440406818136}

S online: {"cP": 0.012562366115083276, "cSmF": 0.012341017510877248, "cS": 0.013137115477411466, "cSaa": 0.013115076344495543, "cSX": 0.01312026221556807, "cSmS": 0.013436895182530257, "cSF": 0.012260200850903498, "cSI": 0.013120398690392913}

Rank stage: {"per_attempt_cost_kP_over_kS": {"estimate": 3.3748616631410577, "ci95": [3.0913883795982278, 3.6805716518585623], "attempts": [1200, 1200], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}, "rank_stage_kP_over_kS": 3.373732037985617, "single_process_e2e_kP_over_kS": 3.2397128277663323, "per_attempt_cost_kSmF_over_kS": {"estimate": 0.9427042230544957, "ci95": [0.8740422091606066, 1.0207168931379351], "attempts": [1200, 1200], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}, "rank_stage_kSmF_over_kS": 0.9427326838900981, "single_process_e2e_kSmF_over_kS": 1.027417538398008, "per_attempt_cost_kSmS_over_kS": {"estimate": 1.0244104385475832, "ci95": [0.948911887922943, 1.1043256152822445], "attempts": [1200, 1200], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}, "rank_stage_kSmS_over_kS": 1.0244013706896415, "single_process_e2e_kSmS_over_kS": 1.0229765195324092, "per_attempt_cost_kS_over_kSaa": {"estimate": 0.9997485651297516, "ci95": [0.9265988168507793, 1.0740709286289436], "attempts": [1200, 1200], "bootstrap": "independent resampling of attempts per arm, 2,000 draws"}, "rank_stage_kS_over_kSaa": 0.9997501128450625, "single_process_e2e_kS_over_kSaa": 0.9999032975546354}

Checks: {"all_executed_rows_valid": true, "one_scalar_per_point_ic_and_rho": true, "oracle_replay": true, "one_relation_per_point_every_ic_process": true, "probe_identities": true, "q0_matches_archived_feistel_identity": true, "rank_tables_equal_archived": true, "rank_relations_and_probes_identical_across_layouts": true, "receipt_matches_schedule": true, "every_scheduled_row_present": true, "all_points_complete": true}

Controls: {"aa_e2e_inside_0.97_1.03": true, "aa_cold_inside_0.97_1.03": true, "planted_lower_bound_above_1": true}
