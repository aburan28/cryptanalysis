# Graph-aware Eisenstein representatives for fixed-generator scalar multiplication

Selecting the nine Eisenstein representatives after exact 33-edge row
matching saved **24,123 point-operation proxy units (5.12%)** on the
frozen 2,048-scalar holdout. The selector uses the same 93,533,616
bytes of balanced pair tables and 28,672-byte matching atlas as the
graph33 baseline. It changed the representative for 1,253 holdout
scalars, saved 2,343 mixed additions, and used 330 additional tau
steps. All 4,444 native scalar outputs in the differential replay
matched the baseline and the independent expected-point controls.

## Method and screen

The baseline ranks nine nearby representatives by a point proxy before
matching their 13 comb columns. The new mode computes all nine width-six
digit streams, forms each stream's 12-row active masks, and looks up the
maximum-matching cardinality in the graph33 atlas. For each valid
representative it scores

`5 * tau_steps + 11 * (unfused_mixed_additions - matched_edges)`,

including sparse top-row repair. It selects the minimum and breaks ties
by the existing norm-ranked order. The baseline representative remains
among the nine choices, so the proxy cannot grow for an individual
scalar. The evaluator then follows the existing graph33 table lookup
and point-addition path. The new native mode is
`--scalar-w6-comb13-hex9-graphaware33-fixed`; the baseline remains
available as `--scalar-w6-comb13-hex9-graph33-fixed`.

The [protocol](GRAPH_AWARE_COVER_PROTOCOL.md) and
[independent checker](graph_aware_cover_screen.py) were committed in
`42264c3a` and opened as draft PR #539 before the holdout was drawn.
Two disjoint panels each contain 2,048 uniform scalars from `[0,n)`.
The checker validated the baseline representative, tau count, repair,
fusion count, and mixed-addition count against the native executable
on the first 128 cases of each panel.

| Panel | Cases | Baseline proxy | Graph-aware proxy | Saving | Baseline mixed adds | Graph-aware mixed adds | Changed representative |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Design | 2,048 | 470,957 | 447,500 | 23,457 (4.98%) | 32,427 | 30,155 | 1,202 |
| **Frozen holdout** | **2,048** | **471,212** | **447,089** | **24,123 (5.12%)** | **32,442** | **30,099** | **1,253** |

The holdout contains 847 zero-gain cases; every per-case rank and cost
delta is retained in the [holdout receipt](graph-aware-cover-holdout.json).
The baseline made 15,849 pair fusions and the new selector made 19,360.
The declared proxy counts five field products per ordinary tau step and
eleven per ordinary mixed addition. It omits the added mask scoring,
table lookup, cache misses, and exceptional point paths; the screen
therefore measures point-work savings rather than online CPU speed.

## Correctness, resources, and next measurement

The [differential verifier](graph_aware_cover_verify.py) checked five
boundary scalars, 214 prior frozen inputs, 129 fixtures with recorded
expected points, and both new panels: **4,444 outputs** in all. It
checked selected representatives, valid-choice counts, tau steps,
repairs, pair fusions, mixed additions, and final points. An independent
Python secp256k1 multiplier checked 261 points. The existing 51
release tests passed after the selector was added; its new focused
native unit check passed separately. The [verification
receipt](graph-aware-cover-verify.json) records source and binary hashes
and aggregate counts.

The new selector retains nine 162-position packed digit streams and
scores 13 row masks per valid representative. Its full CPU effect
depends on that work and memory behavior. The
[paired manifest generator](make_graph_aware_isolated_manifest.py)
uses the same 129 fixture points for seven repetitions per variant,
charging all nine recodings, selection, table access, point work,
affine conversion, and correctness assertion inside the online
interval. The available RunPod pod fails the host-level isolation
preflight, so a controlled CPU ratio requires a qualifying physical
host. The generator produced a 129-case, seven-repeat local manifest;
`isolated_bench.require_manifest` accepted its schema. Its example CPU,
NUMA, and cgroup values are placeholders for a future qualified host.

| Artifact | SHA-256 |
| --- | --- |
| Protocol | `48c99a93180c50a6ff48e1e2c83fa77a67dc8c1c51818d2553a744ad3400b12d` |
| Screen source | `444546c6dfebf3f1985a58dfaa2479eb5827e24b4271faa0326e291d199ffda5` |
| Design receipt | `52b72bf0126adc327bc41cb047884b022fd4e7f8e2a14a243fa8fd36c6c2fe5d` |
| Holdout receipt | `c985a3a40aea6e8c794ef52649849f8f52e6fabf4cd33b4c2b1fa89bfee23f63` |
| Verifier source | `e2558f5a8752ec35afc6b1cb26c6bf30b7b3cc82f2d2bce35de4b2f1183a3902` |
| Verification receipt | `c8fe4ace2dda705b0122150377a2cb8e3d58924d2928b2e4a834de0815b4cd57` |
| Native source | `22f2b0b1580106070484cf1eba879ad1f4915de0530220dbb7e669c343d7f6e1` |
| Candidate release binary | `fbd46d82b7b7867b4bf71dedc46b8ef8a43dd552a94b3779158b347ee1e40b80` |

The next experiment is the complete paired online panel on a host
passing `docs/ISOLATED_BENCHMARKS.md`, followed by a broader prior-art
review of joint recoding and precomputed matching selection.
