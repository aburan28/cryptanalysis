# Q1420 selector-derived coordinate-cut scoreboard

The [selector-cut gate](../ecc2k130-263-selector-cut-20261010/RESULT.md)
uses the equal-`B=16,772,828` source and oriented degree-263 descendant W24
bases on the first public Q0 point of workload `eee7f6ee5f6b`. Its exact
protocol, eight common masks, 36 complete-input hashes, solver transcripts,
and independent audit are committed together. Q1420 remains
`candidate_id: null`.

| Gate | Source | Descendant | Decision |
| --- | --- | --- | --- |
| Archived full-x x0/x5 controls with derived x units | 2/2 `SAT_VERIFIED_GROUP`; 0 final conflicts | 2/2 `SAT_VERIFIED_GROUP`; 0 final conflicts | Selector-derived x/z arithmetic and full model/group replay pass. |
| Eight public-Q0 `selector_only` first-mask branches | 0 verified decompositions; 3 conflict caps, 5 wall caps | 0 verified decompositions; 5 conflict caps, 3 wall caps | Search statuses are censored; no useful row for rank. |
| Same eight public-Q0 `coordinate_cut` branches | 0 verified decompositions; 3 conflict caps, 5 wall caps | 0 verified decompositions; 4 conflict caps, 4 wall caps | Exact x/z cuts did not resolve an ordinary branch under the frozen caps. |

The four eight-branch arms spent 344.428, 329.971, 277.766, and
281.023 seconds in solver wall intervals, respectively, plus 15.210 seconds
of per-branch preparation in total; all were exploratory on an unisolated
host. Common-mask selection took 16.143 seconds as reusable preparation.
The [uniform-group-sum calculation](../ecc2k130-263-selector-cut-20261010/runs/R1/uniform_model.json)
gives an upper expected representation count of `3.25096e-5` per fixed
first mask and `2.60077e-4` over these eight masks **under its stated
distributional assumption**. It is a model-based branch-coverage diagnostic,
not observed relation yield.

The next implementation gate is an exact free-selector constraint using
`alpha*x*z=(x+alpha)^2`, compared on pinned control and held-out ordinary
inputs with complete construction, search, relation, rank, and resource
records. The prior [component scoreboard](Q1420_COMPONENT_SCOREBOARD.md)
retains the matched Gaussian-selection evidence; no solver-stage result here
substitutes for a verified single-target IC/rho comparison.
