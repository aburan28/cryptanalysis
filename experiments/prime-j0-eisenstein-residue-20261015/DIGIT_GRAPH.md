# Adaptive addition graph for scalar-local Eisenstein digits

The native projective `31+32τ` path can share work between the digit points selected by one scalar. The [hash-guarded overlay](native_sparse_digit_graph_overlay.py) treats the selected lattice pairs as vertices, roots an addition graph at `(0,0)`, and grows it by the least estimated group-addition cost. An edge from `(a,b)` to `(c,d)` synthesizes `(c-a)G+(d-b)τG` from a shared eight-bit dyadic basis and adds the already constructed parent. The direct root edge remains available for every target, so graph selection cannot exceed independent synthesis under this operation-count model. The model omits graph-search overhead and differing group-operation costs; wall time decides whether the change helps.

The [Lean theorem module](DigitGraph.lean) checks the lattice displacement identity and its transfer through any point map that preserves addition. Its hypotheses expose the source-level bridge: the native dyadic builder must evaluate the displacement and `add_projective` must implement point addition. The independent native fixture checks below test those implementation links.

## Frozen Tier 1 panels

The [one-scalar](tier1-tau32-digit-graph-1-cpu40-manifest.json) and [128-point](tier1-tau32-digit-graph-128-cpu40-manifest.json) manifests were committed before dispatch. Both compare the graph path with the verified independent projective builder on the same inputs, CPU 40, 16 alternating repeats, and adjacent reference/reference A/A controls. Their [rules](tier1-tau32-digit-graph-1-cpu40-rules.json) and [rules](tier1-tau32-digit-graph-128-cpu40-rules.json) fix the acceptance gate. Rust `Instant` covers scalar-local preparation and Horner evaluation; fixture loading, process launch, and external replay are outside the interval.

| Workload | Independent builder mean | Graph builder mean | Qualified paired reference/graph median | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| One scalar | 0.543 ms | 0.530 ms | 1.020× | [1.010, 1.022] |
| 128 points | 39.983 ms | 38.859 ms | 1.027× | [1.024, 1.032] |

The [independent auditor](analyze_tier1_tau32_digit_graph.py) verified source and binary hashes, all raw commands/stdout/stderr and pair records, the measured fixture points by independent scalar multiplication, stable artifacts, and every A/A control. Each panel completed **96 valid arms and 48 valid pairs**. The [one-scalar launch](tier1-tau32-digit-graph-1-cpu40-launch.json), [audit](tier1-tau32-digit-graph-1-cpu40-audit.json), and [raw archive](tau32-digit-graph-1-raw.tar.gz) identify job `29a9d3b4552b4d809b9d4462738cb291`. The [128-point launch](tier1-tau32-digit-graph-128-cpu40-launch.json), [audit](tier1-tau32-digit-graph-128-cpu40-audit.json), and [raw archive](tau32-digit-graph-128-raw.tar.gz) identify job `b5dcc32046b34c7faf6ad6249d0c0888`. The [provenance archive](tau32-digit-graph-native-provenance.tar.gz) carries both exact source trees and binaries.

## Full-fixture replay

The separately [frozen manifest](tier1-tau32-digit-graph-full-replay-cpu40-manifest.json) and [rules](tier1-tau32-digit-graph-full-replay-cpu40-rules.json) sent two identical graph arms through the serial queue. Job `91167c97ca044280a925af245f13fa82` verified all **12,288** frozen outputs in each arm, with stable artifacts. The [auditor](analyze_tier1_tau32_digit_graph_full_replay.py), [launch](tier1-tau32-digit-graph-full-replay-cpu40-launch.json), [audit](tier1-tau32-digit-graph-full-replay-cpu40-audit.json), and [raw archive](tau32-digit-graph-full-replay-raw.tar.gz) retain the exact record. The two intervals were **3.759 s** and **3.740 s**; this A/A run is a correctness check and has a null speedup field.

The observed improvement is small and specific to the frozen Tier 1 instance. A larger independent replication and an operation-count trace would help separate graph sharing from graph-search overhead across input laws.
