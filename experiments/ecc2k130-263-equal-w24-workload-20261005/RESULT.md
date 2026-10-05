# Equal-size ECC2K-130 W24 input gate

Proposal `Q1420` now has a frozen, independently replayed four-policy input
gate. It is **not** an activated `IC1` candidate or a measured index-calculus
speedup. The sole primary one-target workload is
[`primary_workload.json`](primary_workload.json), ID `eee7f6ee5f6b`. Its one
source public point and verified degree-263 image were selected as corpus
index zero by the published protocol before any PDP result was seen. The
remaining 511 public points belong to the dormant control corpus in
[`workload.json`](workload.json), ID `f417f35ded09`; its ID must not be used
for a single-target IC versus rho claim. The known fixture scalars are in
[`target_fixtures.json`](target_fixtures.json) solely for independent replay.

| Frozen geometry | Signed classes | Actual usable points `B` | Selected ascending-mask stream SHA-256 |
| --- | ---: | ---: | --- |
| Source W24 prefix | 8,386,414 | 16,772,828 | `1372e1938950a4b6e6d2003732ac04102b8f794606669eeffcc5918360484aeb` |
| Native descendant W24 | 8,386,414 | 16,772,828 | `513fa94908281b93ac5598c8f70eca925115e7efd012d7c36fd1859c03049203` |

The source prefix ends at mask `16763440`; the native descendant includes
all masks through `16777215`. The source and descendant full streams were
replayed from their pinned gzip files, with counts `8,393,232` and
`8,386,414` respectively. The native W24 construction uses the normalized
`a4=0` model only as an intermediate. Every stored descendant point lies on
the exact *unnormalized* codomain named by
`EC1N131Cbinh833014327b07`; the intermediate-to-codomain map is
`(x,y) -> (x,y+A)`. The source curve is
`EC1N131Ckb1h136f03e58c98`, and the verified route is
`IW1E263d1hadee4e69fa3d`.

The checked Sage producer reconstructed both degree-263 maps from the
archived kernel polynomials, verified generator transport and dual
composition, and checked 64 source plus 64 native controls on the proper
models. The independent verifier reconstructed the maps separately,
re-read both full mask streams, and replayed all 128 controls and 512
scalar/public-point pairs. Its result is
[`verification.json`](verification.json):
`PASS_EXACT_BASE_ROUTE_AND_PUBLIC_FIXTURES`. A separate pure-Python
[`verify_primary.py`](verify_primary.py) check returned
`PASS_ONE_TARGET_WORKLOAD_ID` for the one-target manifest.

The producer's exploratory wall time was 118.325 s: 51.374 s map setup,
10.707 s controls, and 56.219 s fixture construction. Peak RSS was
266,928,128 bytes. The independent replay took 149.606 s and reached
255,213,568 bytes. Both runs used the checked repository Sage launcher,
with saved [producer](runtime-info.json) and
[verifier](runtime-info-verifier.json) runtime receipts (identical SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).
These times are setup and correctness diagnostics on an unisolated host;
none is a target-online IC or rho measurement.

This gate resolves the base-size confound for the next comparison and proves
the exact public-point model and route wiring on its sampled controls.
Transported source points and their source counterparts have identical
group-sum membership under the subgroup isomorphism; the analogous statement
holds for native points and their pullbacks. That is a mathematical pairing,
not a measured implicit-PDP hit rate. The next PR should preregister an
ordinary-query prefix and bounded W24/m6 PDP implementations on these four
policies, preserve failures and timeouts, and measure verified novel rank
per query and charged map costs. Only after a complete, verified one-target
logarithm and paired same-point rho solve may it report an online speedup.
The `candidate_id`, natural PDP yield, relation rank, matrix cost, target
descent, recovered logarithm, and speedup remain `null` here.

Reproduce the frozen gate from the repository root with the checked launcher:

```sh
python3 experiments/ecc2k130-263-equal-w24-workload-20261005/freeze_base.py --out /tmp/ecc2k130-base-replay.json
./sage --runtime-info > /tmp/ecc2k130-runtime-replay.json
./sage -python experiments/ecc2k130-263-equal-w24-workload-20261005/verify_workload.py --out /tmp/ecc2k130-workload-replay.json
python3 experiments/ecc2k130-263-equal-w24-workload-20261005/verify_primary.py
```

The full producer refuses to overwrite frozen artifacts. To repeat it,
give `freeze_workload.py --out-dir` a fresh output directory; it reads the
repository's pinned config, base selection, and Sage runtime receipt.
