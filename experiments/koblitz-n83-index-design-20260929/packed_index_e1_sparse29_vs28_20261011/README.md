# N83 E-1 sparse29 directory against sparse28

The sparse29 exact root directory reduces full-key target probes from
7,415,319 to 2,381,131 (67.89%) on the frozen N83 single-target,
29,900,000-pair-state stage. It uses 50,331,648 additional root-table bytes
(48 MiB). Both full-capacity modes ran from the same source and agree on all
23 frozen semantic fields, including first-witness certificate
`083d0561e2d3f52763840c10d4c540550b71446daaf09f3d1ef50a53def81a51`.
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
