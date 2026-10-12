# Arithmetic identities stated in run-11 REPORT (overlap formula and modeled edge counts), re-derived from our
# shortest-path computation (c08: 130 non-reference charts, total path length).
import json
from math import comb
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
c08 = json.loads((W / "raw/c08_cm_scalar_algebra.json").read_text())
tot_path = round(c08["A_mean_path_len_130_nonref"] * 130)
codex = {"dup": {0: 0, 4: 2080, 8: 145600, 12: 1029600, 16: 3785600},
         "core_only": {0: 0, 4: 16, 8: 1120, 12: 7920, 16: 29120},
         "edges": {0: 0, 4: 17160, 8: 34320, 12: 51480, 16: 68640}}
res = {"total_shortest_path_length_130_charts": tot_path, "rows": {}}
for c in [0, 4, 8, 12, 16]:
    ours = {"dup": 130*16*comb(c, 4), "core_only": 16*comb(c, 4), "edges": c*tot_path}
    res["rows"][c] = {k: {"codex": codex[k][c], "ours": ours[k], "agree": codex[k][c] == ours[k]} for k in ours}
res["all_agree"] = all(v["agree"] for r in res["rows"].values() for v in r.values())
print(json.dumps(res, indent=1))
(W / "raw" / "c17_run11_arithmetic.json").write_text(json.dumps(res, indent=1))
