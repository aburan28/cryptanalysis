# N83 E-1 sparse29 directory against sparse28

The sparse29 exact root directory reduces full-key target probes from
7,415,319 to 2,381,131 (67.89%) on the frozen N83 single-target,
29,900,000-pair-state stage. It uses 50,331,648 additional root-table bytes
(48 MiB). Both full-capacity modes ran from the same source and agree on all
23 frozen semantic fields, including first-witness certificate
`083d0561e2d3f52763840c10d4c540550b71446daaf09f3d1ef50a53def81a51`.
Eight Tier 1 same-target pairs measure a **1.0473×** median sparse28/sparse29
target-stage wall ratio, with paired bootstrap 95% interval **[1.0253, 1.0625]**.
The [input verifier](verify_inputs.py) checks the raw results, hashes,
control status, phase accounting, memory cap, and release-test receipt.

This is proposal `Q2026101136`, curve `EC1N83Ckb1h876c2921cb64`, and workload
`63dd0929cf33`. The compared measurement begins after target-independent
index and cached point-coordinate setup, then includes target query
preparation, partner generation, canonicalization, exact root lookup, and
native relation checks through the state cap. The complete IC candidate ID
remains `null` until the other pipeline stages are specified. The source hash
is `c563a232b0d456250b59d3e239fc7039957196a5fe7ced1d36626998bb1b1c60`.

| Full-capacity exact observation | Sparse28 | Sparse29 |
| --- | ---: | ---: |
| Indexed pair states | 29,900,000 | 29,900,000 |
| Target full-key probes | 7,415,319 | 2,381,131 |
| Root table bytes | 1,275,567,104 | 1,325,898,752 |
| First-witness certificate | same | same |

The sparse28 raw result is the exact replay archived with the merged sparse30
comparison; sparse29's new local raw result and launch record are in
`screen_sparse29.json` and `screen_sparse29.record.json`. Local timing is
exploratory because that host was not isolated. The prior sparse30 Tier 1
panel measured a regression despite fewer probes, so this candidate tests
whether the smaller 29-bit directory avoids that lookup cost.

`comparison_protocol.json` freezes both modes, source and input hashes, exact
result fields, 5,500 MiB RSS cap, and the one-target timing boundary.
`tier1_protocol.json` binds that protocol by SHA-256 and fixes eight
alternating pairs with a 300-second cap per arm. The workflow
`.github/workflows/n83-e1-sparse29-vs28-tier1.yml` builds one release binary
and runs the repository Tier 1 instance preflight and paired runner. A
stage wall-time gain is eligible only after all eight exact pairs pass memory
and observed noise gates and the paired 95% bootstrap lower bound exceeds one.

## Tier 1 result

The [GitHub Actions run](https://github.com/aburan28/cryptanalysis/actions/runs/38198612069)
completed eight alternating pairs on instance
`gh-38198612069-1-paired-stage`. All 16 raw arms passed the frozen exact
result, memory, and observed noise checks. All eight pair ratios exceed one.
`verify_tier1_receipt.py` independently replays the archived raw outputs,
allocation, preflight, artifact hashes, phase sums, and paired bootstrap
calculation in `tier1_github_38198612069/`.

| Tier 1 target-stage measure | Sparse28 | Sparse29 |
| --- | ---: | ---: |
| Median online wall, seconds | 49.323 | 46.823 |
| Median target process CPU, seconds | 49.316 | 46.816 |
| Median query preparation, seconds | 4.744 | 4.749 |
| Median partner generation, seconds | 18.708 | 18.714 |
| Median partner check, seconds | 25.851 | 23.328 |
| Maximum native RSS, bytes | 5,308,686,336 | 5,371,076,608 |

The paired median sparse28/sparse29 wall ratio is **1.0473273**, with paired
bootstrap 95% interval **[1.0253336, 1.0624546]**. The improvement is
instance-scoped and specific to the bounded target-dependent PDP stage and
frozen N83 target. The separate sparse26/sparse28 Tier 1 run used another
instance, so this result is reported directly against sparse28.
