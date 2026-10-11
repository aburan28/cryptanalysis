# E-1 packed N83 root-index capacity at 29.9 million states

The sparse 24-bit packed root index with cached polynomial x/y coordinates
completed **29,900,000** sampled pair states and stored **59,799,706** distinct
exact root keys under a **5,500 MiB** process RSS cap. Peak RSS was
**5,355,683,840 bytes**, leaving **411,484,160 bytes** below the cap. This
tests the state-count and memory premise of E-1 at the proposed scale. The
run's native target-stage status was `state_cap_no_relation` after scanning
all 29,900,000 states.

## Frozen input and implementation

| Item | Value |
| --- | --- |
| Curve | `EC1N83Ckb1h876c2921cb64`; field size `2^83` |
| Subgroup order | `2417851639230796216685689` |
| Public target `(x,y)` in polynomial encoding | `(7378557141477440425043731, 6374944737560147782643405)` |
| Usable factor-base points; folded columns | `30,977,592`; `186,612` |
| State law | Coprime-stride sample without replacement of quotient pair states; one orientation per state |
| Workload ID | `63dd0929cf33`; distinct from the 2M-state workload `981ac530e67e` |
| Proposal ID; candidate ID | `Q2026101129`; `null` pending a complete IC pipeline |
| Native source SHA-256 | `33a3c06141c82142efd11fe9f82540761bc361985383cb49c5eb03d28055824a` |
| Rebuilt macOS ARM64 binary SHA-256 | `d385224f3bcdf4fed08840a0fd312952e909f0ac909444a2048c3b4b7e3fb2b5` |
| Index mode | `packed_sparse24_compact16_cachedxy` |
| Index cap; RSS cap | `29,900,000` states; `5,500 MiB` |

The binary was rebuilt from the frozen source and matched the earlier
[cached-coordinate build receipt](../packed_index_e1_cachedxy_cpu_20261011/build_receipt.json)
byte for byte. From this directory, the build command was:

```sh
mkdir -p target
CARGO_TARGET_DIR="$PWD/target" TMPDIR="$PWD/target" \
NATIVE_S3_SOURCE_SHA256=33a3c06141c82142efd11fe9f82540761bc361985383cb49c5eb03d28055824a \
NATIVE_S3_BUILD_MANIFEST_SHA256=7f3282483caf608a23850e33d845faf825a960263ea22c84ded567425860cd88 \
cargo build --release --locked --offline \
  --manifest-path ../packed_index_e1_cachedxy_cpu_20261011/Cargo.toml
```

The source, representative set, bridge, parent manifest,
runner, workload, and binary hashes were frozen in [protocol.json](protocol.json)
before the measured run. [verify.py](verify.py) checks those bindings, the
raw output digest, the count and cap, the native control, and phase
accounting. Run it with `python3 verify.py` from this directory. A fresh
replay directory can run `python3 capacity_probe.py prepare --binary
target/release/native_packed_index` followed by `python3 capacity_probe.py
run --binary target/release/native_packed_index`; the producer preserves its
first receipt by refusing to overwrite an existing run.

## Measured capacity and stage costs

| Measurement | Value |
| --- | ---: |
| Index pair states examined; target states scanned | 29,900,000; 29,900,000 |
| Distinct root keys; root-table allocation | 59,799,706; 1,027,054,592 bytes |
| Cached root x; cached root y allocation | 956,800,000; 956,800,000 bytes |
| Peak RSS; cap headroom | 5,355,683,840; 411,484,160 bytes |
| Index build wall; process CPU | 38.790 s; 21.519 s |
| Root lift wall within index build | 13.323 s |
| Target query preparation wall | 5.288 s |
| Target partner generation wall | 16.336 s |
| Target partner check wall | 123.748 s |
| Other charged target time | 0.051 s |
| Total target-stage wall; process CPU | 145.423 s; 65.097 s |
| Target partner roots; exact-table hits | 119,600,000; 0 |
| Native status | `state_cap_no_relation` |

The target clock starts after index construction and root-coordinate cache
construction. The three named target phases plus the recorded residual equal
the charged target-stage wall time. [run_record.json](run_record.json) retains
the producer exit status, outer elapsed time, child CPU, source-bound output
digest, and absence of a host-isolation receipt. The timings are exploratory
macOS measurements; the repository's physical-host isolation gate is still
required for a controlled wall-time comparison on workload `981ac530e67e`.

The native producer checked an indexed-root lookup sample with its
first-inserted witness and verified its generator/target S3 control. The same
native source was previously audited over all 4,000,000 partner pairs and
8,000,000 roots on workload `981ac530e67e`; this capacity run retains the
new 29.9M-state sample and exact source identity. Its raw producer output is
[run_packed_cachedxy_29900000.json](run_packed_cachedxy_29900000.json).

The next measured comparison is the frozen 2M-state cached-coordinate versus
S3 reference replay on a physical host satisfying the isolation preflight.
At 29.9M states, the unchanged one-orientation query law examined 119.6M
partner roots with zero exact-table hits; changing query coverage or the
collection law is a separate, frozen candidate experiment.
