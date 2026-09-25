# Compare Codex run-10 horizontal-graph.json edge sets with our independently computed neighbours (c03).
import json
from pathlib import Path
W = Path("/Volumes/SSD990/ecdlp-hardness-work/codex-crosscheck")
cx = json.loads((W / "codex_inputs/curve-comparison/run-10-horizontal-isogenies/horizontal-graph.json").read_text())
our = json.loads((W / "raw/c03_horizontal_graph.json").read_text())
res = {}
for r in cx["results"]:
    l = str(r["prime"])
    ce = set(frozenset(e) for e in r["edges"])
    oe = set()
    for lab, nb in our["ells"][l]["neighbours"].items():
        if lab == "E0": continue
        for n, m in nb:
            oe.add(frozenset([lab, n]))
    res[l] = {"codex_edges": len(ce), "our_edges": len(oe), "identical": ce == oe,
              "only_codex": sorted(map(sorted, ce - oe))[:5], "only_ours": sorted(map(sorted, oe - ce))[:5],
              "codex_component_sizes": r.get("component_sizes"), "codex_loops": len(r.get("loops", [])),
              "codex_same_orbit_offsets": r.get("same_orbit_offset_histogram"),
              "codex_cross_orbit_offsets": r.get("cross_orbit_offset_histogram"),
              "our_classgroup": our["classgroup"][l]}
    print(l, {k: v for k, v in res[l].items() if k != "our_classgroup"})
res["classgroup"] = {k: v for k, v in our["classgroup"].items() if not k.isdigit()}
print(res["classgroup"])
(W / "raw" / "c04_compare_horizontal.json").write_text(json.dumps(res, indent=1))
