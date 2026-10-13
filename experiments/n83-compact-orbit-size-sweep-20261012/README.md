# Degree-83 compact-orbit base-size result

**The nested K800 factor base reduced verified single-target online work by
14.45× on one frozen public point relative to K600, and completed the fresh
process 1.24× sooner.** Both candidates used the same degree-83 `a=1`
Koblitz curve, binary, target, rank seed, and thread policy. K800's 800
signed-Frobenius columns represent 132,800 distinct usable subgroup points;
K600's 600 columns represent 99,600. The complete K600 base is an exact
prefix of K800's representatives, point coordinates, and labels. The
K600 base hash matches the retained historical base. Its full dump also
matches the archived K600 file byte for byte.

| One new public point, local shared Mac | K600 | K800 |
| --- | ---: | ---: |
| Usable base points before folding | 99,600 | 132,800 |
| Root-table entries | 29,878,182 | 53,117,564 |
| Index build | 287.591 s | 611.296 s |
| Guided rank | 603.784 s | **108.800 s** |
| Rank / attempts / failed attempts | 600 / 600 / 0 | 800 / 800 / 0 |
| Mean probes per rank relation | 2,327,829 | **1,113,083** |
| Target probes | 3,260,806 | **207,125** |
| Verified target online | 3,630.019 ms | **251.256 ms** |
| Full fresh-process wall | 897.216 s | **722.064 s** |
| Sampled peak RSS | 4.827 GB | 9.354 GB |

The 33.3% increase in useful columns reduced total rank probes from
1,396,697,479 to 890,466,092, a 1.57× reduction. The target found its
first verified relation after 15.74× fewer probes. The larger root table
took 2.13× as long to build and used more memory; the rank reduction was
large enough to lower this run's full process wall. These are one-point
measurements, and first-witness probe counts can vary strongly with the
target and base ordering.

The paired optimized strong-rho worker recovered the **same** scalar before
and after the IC runs. Its online intervals were 6,290.892 and 1,505.515
ms, while both runs had exactly 6,683,774 walk steps and identical full
charge records. The 4.18× wall variation on identical rho work shows why the
local CPU ratios are exploratory. Both IC online intervals include target
query, PDP, relation check, direct descent, and scalar replay; index/rank
preparation is measured separately. The controlled speedup field remains
`null` pending a Tier 1 or Tier 0 paired replay with stable host receipts.

## Exact instance and records

The field is `GF(2^83)` with polynomial
`x^83+x^7+x^4+x^2+1`; the curve is `y²+xy=x³+x²+1`.
Its prime subgroup has order `8,569,786,107,849,059` and cofactor
`1,128,547,018`. The base constructor scans successive polynomial-basis
`x` words, lifts rational points, projects by the cofactor, and keeps the
first K distinct signed-Frobenius orbits. The public target is stored in
[`target.jsonl`](target.jsonl); its fixture scalar is held only in the
[`validation sidecar`](validation_sidecar.json) and is never passed to either
worker. The exact source commit is `6600c7c6c0cfbb6a9e4e596bf8c5cfa292fb269e`.

The [frozen protocol](protocol.json) fixes the single target, arm order,
12 rank threads, one target thread, rank seed 29, tuned rho policy, 40-minute
IC process cap, 60-second rho cap, and 12 GiB sampled RSS stop. Each IC arm
starts with empty index and log state. The [execution receipts](runs/)
retain command, binary and input hashes, raw stdout/stderr, target row, full
point-defined base dump, process wall, RSS samples, and disposition.

The [independent verification](verification_v2.json) checks 51 exact
conditions, including full-rank completion, all five target phase sums,
the four-point relation via separate Python `GF(2^83)` arithmetic, scalar
replay, exact base nesting, rho's identical walk charges, and all artifact
hashes. The separate [full-base replay](full_base_replay.json) checks every
one of the 232,400 point and label rows, all 1,400 representatives in the
prime-order subgroup, complete 166-point orbits, and distinct orbit keys.
The first passing [receipt](verification.json) remains frozen; v2 adds the
equal-rho-charge check. The [identity verifier](verify_identities.py)
recomputes the curve, workload, candidate, run, and enumerated-set hashes
from the [candidate manifests](candidate_K800.json) and
[`measurements_v2.json`](measurements_v2.json). The original measurement
rows remain in [`measurements.json`](measurements.json); v2 binds the later
full-base replay by digest. The K600 manifest is
[`candidate_K600.json`](candidate_K600.json).

To replay the read-only checks after checking out the pinned crypto commit:

```sh
N83_CRYPTO_REPO=/path/to/crypto-at-6600c7c6 python3 experiments/n83-compact-orbit-size-sweep-20261012/verify.py
python3 experiments/n83-compact-orbit-size-sweep-20261012/verify_identities.py
```

For a fresh run, set `N83_CRYPTO_REPO` and `N83_BIN_DIR` to a clean checkout
and its two release example binaries, stage the frozen protocol and input in
an empty run directory, build with
`cargo build --release --locked --offline --example koblitz_orbit_dlp_fast
--example n83_rho_optimization_eval`, and execute `run.py`. The scripts refuse
to overwrite frozen outputs. Live RSS polling needs host permission to read
the child process. The standalone crypto source has no local Sage dependency.

## Next decision

This screen identifies K800 as the stronger completed candidate at this
point and memory envelope. The next bounded size test should compare K800
and K900 on a separately frozen public point with the same source and 12 GiB
cap. A held-out target panel is then needed to estimate target-probe and rank
variation; a Tier 1 RunPod or Tier 0 host replay with paired optimized rho
is needed for a qualified wall-time comparison. The search over base shapes,
sizes, target laws, and resource envelopes remains open.
