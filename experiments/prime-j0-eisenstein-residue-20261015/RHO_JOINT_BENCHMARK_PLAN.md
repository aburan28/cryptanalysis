# Target-charged joint rho benchmark plan

The first comparison measures one frozen secp256k1 restart point `aG+bQ` with
target-specific Q preparation charged to the joint candidates. A 128-restart
panel follows as a separate batch question. Both panels pair the public
scalars and Q point with the no-warmup OpenSSL reference in the same Linux
binary on the existing RunPod allocation `thyvmdqmzsz5ik`, through its serial
benchmark queue.

## Frozen arms and boundaries

The [fixture](rho-restart-first128-fixture.json) has SHA-256
`fc6a0283c51e3fd9c2eb0b82961092d3060c242d8122c9648c37fdaf614d094a`.
The one-restart panel uses its first case; the batch panel uses its first 128
cases. Each panel runs 16 alternating repetitions of these nine cases:

| Case | Reference | Candidate |
| --- | --- | --- |
| `cal_before` | OpenSSL no-warmup | OpenSSL no-warmup |
| `compare_demand` | OpenSSL no-warmup | Sparse Q table and shared Horner |
| `compare_graph` | OpenSSL no-warmup | Shared Q-seed graph and shared Horner |
| `compare_graph_planned` | OpenSSL no-warmup | Precompiled scalar graph and shared Horner |
| `cal_mid` | OpenSSL no-warmup | OpenSSL no-warmup |
| `compare_fused` | OpenSSL no-warmup | Sparse Q table, batched affine pair sums, shared Horner, batched output normalization |
| `compare_fused_graph` | OpenSSL no-warmup | Shared Q-seed graph followed by batched affine pair sums and output normalization |
| `compare_fused_graph_planned` | OpenSSL no-warmup | Precompiled scalar graph followed by batched pair sums and output normalization |
| `cal_after` | OpenSSL no-warmup | OpenSSL no-warmup |

All seven distinct commands time affine serialization. OpenSSL's interval starts at
its first `EC_POINT_mul` for the public `a,b,Q` and includes every requested
restart. Its Q parsing and curve construction precede the timer. The joint
commands exclude globally reusable G and canonical-seed preparation; their
`online_ms` includes Q parsing and table construction, a-scalar recoding,
restart evaluation, and affine output. Direct and online graph arms also
charge b-scalar recoding. The two planned graph arms compile the b-scalar
choices and graph topology without using Q, report that separate
`graph_plan_ms` and `plan_bytes`, and charge graph instantiation on Q online.
The auditor preserves mean graph-plan, target-preparation, and evaluation
times by mode; `graph_plan_ms + online_ms` is a supplementary cold interval
for the planned modes. Plan reuse requires the declared scalar stream to
remain fixed across target points.
The joint boundary is therefore
conservative with respect to reference Q parsing. Fixture reading, input
decoding, process launch, and independent expected-point checks are outside
every timed interval. The joint commands report target preparation and
evaluation as exclusive phase costs whose sum is `online_ms`.

Each panel has 144 planned pairs and 288 arms, including 48 OpenSSL A/A
control pairs. The queue runs one subprocess at a time on CPU 40. The Tier 1
receipt must retain exposed topology, affinity, cgroup limits, throttling,
steal time, memory and calibration noise. A comparison advances only when
all 16 pairs for that case are valid, the bracketing A/A controls lie within
`[0.90,1.11]`, the paired bootstrap 95% log-ratio interval excludes one,
and every point independently replays. A failed or noisy arm stays in the
ledger and leaves the corresponding aggregate unknown.

## Build, freeze, and dispatch sequence

1. After the source-transfer approval, copy the approved overlay, joint
   module, and rho command module to the existing Pod. Apply the
   [hash-guarded overlay](native_rho_restart_joint_overlay.py) to a fresh copy
   of the archived hybrid source. Build the x86-64 release binary offline;
   preserve its stdout, stderr, compiler version, source hashes, linked
   `libcrypto`, and binary hash. The overlay adds the `openssl_nowarm` mode by
   patching the archived helper at its checked hash.
2. Replay counts 1 and 128 in `openssl_nowarm`, `joint_demand`,
   `joint_graph`, `joint_graph_planned`, `joint_fused`,
   `joint_fused_graph`, and `joint_fused_graph_planned` modes before timing.
   The local [correctness receipt](joint-q-graph-local-replay.json) contains
   1,268 exact outputs on macOS ARM64, including affine edge cases. Linux replay is required
   for the native x86-64 build.
3. Read the deployed binary and `libcrypto` SHA-256 values. Run
   [make_tier1_rho_joint.py](make_tier1_rho_joint.py) locally with those hashes
   to write both manifest/rules pairs. The generator rebuilds the expected
   source tree from the archived base and current overlay; compare its hashes
   with every deployed artifact before submission. The generator's local
   dry run validated both nine-case manifests. Its dry-run binary hash came
   from macOS and must be replaced with the Linux binary hash.
4. Submit only the **one-restart** manifest to the live serial queue. Wait
   for a terminal queue result, archive raw stdout/stderr, run/pair ledgers,
   host counters, preflight and postflight, then audit all source hashes,
   output points, A/A ratios, and paired uncertainty. Submit the 128-restart
   panel only after the one-restart result is recorded. Preserve the panels
   separately; the 128 result answers batch amortization.

Run the independent [joint receipt auditor](analyze_tier1_rho_joint.py) on
each archived panel with its Linux-hash manifest and rules. For example:

```sh
python3 analyze_tier1_rho_joint.py 1 \
  --manifest tier1-rho-joint-1-cpu40-manifest.json \
  --rules tier1-rho-joint-1-cpu40-rules.json \
  --raw rho-joint-1-raw.tar.gz \
  --output tier1-rho-joint-1-cpu40-audit.json
```

The auditor reconstructs the generated source hashes, independently replays
the fixture points, verifies all available arm records and exact pair order,
checks the joint phase sums and OpenSSL zero-warmup field, and gates each
comparison on all three A/A controls. A partial pair remains in the ledger;
the aggregate stays unknown. The command is for a completed archived Linux
panel; the local manifest dry run has a macOS binary hash and is not a panel.

The [seed graph method](JOINT_SEED_GRAPH.md) is an additional candidate in
this panel. Its local exact-output receipt has 1,268 outputs. The archived
OpenSSL hybrid panel's one-restart A/A gate previously failed;
this plan retains the same strict gate and uses a middle A/A control between
the shared-Horner and fused-pair candidate groups. The queue service was observed live as PID 2098 on the
named Pod, with Tier 1 support in its running script. The allocation receipt
still identifies `thyvmdqmzsz5ik` as RunPod, and its current `libcrypto.so.3`
hash is `d6fc1bc9de29c55fc905f77edba1ccc7c7a50b32bd2bb9086b0d0b00104eafc4`.
Pod-level CPU pinning defines this as Tier 1; no physical-host isolation
certificate is inferred.
