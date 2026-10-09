# Joint graph and representative design: frozen screen

Re-optimizing the three long pair-table edges for graph-aware
representatives selected `(0,11)`, `(0,7)`, and `(1,11)`. The parent
graph used `(0,11)`, `(0,8)`, and `(1,11)`. On the frozen 4,096-scalar
holdout, the new graph's point-operation proxy was **896,108**, versus
**895,978** for the parent, so the 0.5% improvement gate was not met.
The candidate is stopped at screening; its full pair table was not
built.

## Frozen rule and result

The [protocol](JOINT_GRAPH_PROTOCOL.md) and
[checker](joint_graph_screen.py) were committed in `c43da510`
and opened as draft PR #540 before the design and holdout scalars
were generated. The checker used 2,048 design scalars from seed
`20261009421` and 4,096 disjoint holdout scalars from seed
`20261009422`, uniformly drawn from `[0,n)`. Starting from the 30
edges of row distance at most three, each greedy step tried every
remaining edge and reselected the best of nine Eisenstein
representatives for every design scalar. The native parent selector's
representative, tau count, repair, pair fusions, and mixed additions
matched the independent checker on the first 128 cases of each panel.

| Panel | Parent proxy | Joint graph proxy | Change | Per-scalar regressions | Zero-change cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| Design, 2,048 | 447,801 | 447,648 | 153 fewer (0.034%) | 95 | 1,846 |
| **Holdout, 4,096** | **895,978** | **896,108** | **130 more (0.015%)** | **217** | **3,669** |

Both graphs store 33 complete edge tables, requiring 93,533,616
retained slot bytes. The design search favored `(0,7)` over `(0,8)`;
that choice did not transfer to the holdout. Both
[design](joint-graph-design.json) and [holdout](joint-graph-holdout.json)
receipts preserve all per-case ranks, proxy deltas, input hashes,
edge lists, and atlas hashes. There were no screen failures.

## Complete-graph ceiling

A [post-hoc diagnostic](joint_graph_ceiling.py) computes the best proxy
available to this same nine-representative, 13-column, pair-only
scheme if every one of the 66 row edges were stored. For an active
mask with `k` rows, any pair matching has at most `floor(k/2)` edges;
the complete graph attains that count. Taking the best of the same
nine representatives therefore gives a lower bound on the point
proxy for *any* pair-edge subset on each frozen scalar.

| Panel | Parent graph proxy | Complete-graph proxy | Maximum further saving under this model |
| --- | ---: | ---: | ---: |
| Design, 2,048 | 447,801 | 428,726 | 19,075 (4.26%) |
| Holdout, 4,096 | 895,978 | 857,167 | 38,811 (4.33%) |

The complete graph would require **187,067,232 retained slot bytes**
at the current 72-byte format, above the 90 MiB cap. Its proxy is a
mathematical ceiling on pair-fusion savings for these input streams,
not a measured implementation. The failed greedy result leaves room
for a different 33-edge optimization rule or a denser storage format.
The ceiling is retrospective and did not select the stopped candidate.

| Artifact | SHA-256 |
| --- | --- |
| Frozen protocol | `2435db7175e0d865272e84131a3d511c8ecaeca7d50cc6cbdd9ad82b32f34463` |
| Screen source | `be7b33acb02547378ac05037fd4cf5d251b8409240d24696cf0340c9d86efb51` |
| Design receipt | `e452eb96a55c79c8a7f2bc8e9f5f01b094818eeae6f47313b880f0051e34c404` |
| Holdout receipt | `eb5a14ee73a151068dd3593c0b442a2d70195fa83eed8fbced4510553a451f6d` |
| Ceiling source | `a31418dfd71ea1564e592ef10987177798c9184e8c8c7730e396b0282478de84` |
| Ceiling receipt | `788ff97ad370531c916ba6f64255110a60bf53c38b6a90de1d9c650da0a3d648` |

The next graph-design test should allow replacing any of the 33 edges
while reselecting representatives, with a new frozen design and
holdout panel. A controlled online CPU comparison remains pending on
a host passing `docs/ISOLATED_BENCHMARKS.md`.
