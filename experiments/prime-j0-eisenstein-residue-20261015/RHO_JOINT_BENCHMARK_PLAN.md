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
cases. The one-restart panel runs 22 cases and the 128-restart panel runs 20;
each case has 16 alternating repetitions:

| Case | Reference | Candidate |
| --- | --- | --- |
| `cal_before` | OpenSSL no-warmup | OpenSSL no-warmup |
| `compare_demand` | OpenSSL no-warmup | Sparse Q table and shared Horner |
| `compare_graph` | OpenSSL no-warmup | Shared Q-seed graph and shared Horner |
| `compare_graph_planned` | OpenSSL no-warmup | Precompiled scalar graph and shared Horner |
| `compare_root_first` | OpenSSL no-warmup | Root-first graph and shared Horner |
| `compare_weighted` | OpenSSL no-warmup | Low-rotation graph and shared Horner |
| `compare_weighted_vs_root_first` | Root-first graph | Low-rotation graph, same scalar stream and Q |
| `compare_two_parent` | OpenSSL no-warmup | Two-parent graph and shared Horner |
| `compare_two_parent_vs_root_first` | Root-first graph | Two-parent graph, same scalar stream and Q |
| `compare_steiner` | OpenSSL no-warmup | Auxiliary-vertex graph and shared Horner |
| `compare_steiner_vs_two_parent` | Two-parent graph | Auxiliary-vertex graph, same scalar stream and Q |
| `compare_refined` | OpenSSL no-warmup | Refined graph and shared Horner |
| `compare_refined_vs_prior` | Auxiliary-vertex graph for one restart; low-rotation graph for 128 | Refined graph, same scalar stream and Q |
| `compare_one_aux` (one restart) | OpenSSL no-warmup | One-auxiliary graph and shared Horner |
| `compare_one_aux_vs_refined` (one restart) | Refined two-auxiliary graph | One-auxiliary graph, same scalar stream and Q |
| `compare_unit_root` (one restart) | OpenSSL no-warmup | Unit-root graph and shared Horner |
| `compare_unit_root_vs_one_aux` (one restart) | One-auxiliary graph | Unit-root graph, same scalar stream and Q |
| `compare_mixed_cost` (128 restarts) | OpenSSL no-warmup | Cost-aware mixed-addition graph and shared Horner |
| `compare_mixed_cost_vs_weighted` (128 restarts) | Low-rotation graph | Cost-aware mixed-addition graph, same scalar stream and Q |
| `cal_mid` | OpenSSL no-warmup | OpenSSL no-warmup |
| `compare_fused` | OpenSSL no-warmup | Sparse Q table, batched affine pair sums, shared Horner, batched output normalization |
| `compare_fused_graph` | OpenSSL no-warmup | Shared Q-seed graph followed by batched affine pair sums and output normalization |
| `compare_fused_graph_planned` | OpenSSL no-warmup | Precompiled scalar graph followed by batched pair sums and output normalization |
| `cal_after` | OpenSSL no-warmup | OpenSSL no-warmup |

All candidate commands time affine serialization. OpenSSL's interval starts at
its first `EC_POINT_mul` for the public `a,b,Q` and includes every requested
restart. Its Q parsing and curve construction precede the timer. The joint
commands exclude globally reusable G and canonical-seed preparation; their
`online_ms` includes Q parsing and table construction, a-scalar recoding,
restart evaluation, and affine output. Direct and online graph arms also
charge b-scalar recoding. The planned graph arms load separately frozen
artifact of b-scalar choices and graph topology. The artifact contains no Q
and is hashed in the panel manifest. They report `plan_load_ms` and
`plan_bytes`, and charge graph instantiation on Q online. The auditor preserves
plan-load, target-preparation, and evaluation times by mode. Plan generation
and loading are separate setup costs; reuse requires the declared scalar
stream to remain fixed across target points. The low-rotation versus root-first,
root-first versus two-parent, two-parent versus auxiliary, refined versus
its immediate predecessor, one-auxiliary versus refined, and unit-root versus
one-auxiliary, and cost-aware versus low-rotation pairs apply the same planned-command
timing boundary to both arms, so each ratio isolates graph construction on
the same Q.
The joint boundary is therefore
conservative with respect to reference Q parsing. Fixture reading, input
decoding, process launch, and independent expected-point checks are outside
every timed interval. The joint commands report target preparation and
evaluation as exclusive phase costs whose sum is `online_ms`.

The one-restart panel has 352 planned pairs and 704 arms; the 128-restart
panel has 320 pairs and 640 arms. Each includes 48 OpenSSL A/A control pairs.
The queue runs one subprocess at a time on CPU 40. The Tier 1
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
   Supply the distinct frozen lexicographic, root-first, low-rotation,
   two-parent, auxiliary, refined, one-auxiliary, unit-root, and cost-aware plan
   files to the planned graph mode. The
   [graph-order and auxiliary replays](../joint-seed-spanning-forest-20261016/README.md)
   check both graph evaluators with alternate Q points.
   The local [correctness receipt](joint-q-graph-local-replay.json) contains
   1,268 exact outputs on macOS ARM64, including affine edge cases. Linux replay is required
   for the native x86-64 build.
3. Read the deployed binary and `libcrypto` SHA-256 values. Run
   [make_tier1_rho_joint.py](make_tier1_rho_joint.py) locally with those hashes
   to write both manifest/rules pairs. The generator rebuilds the expected
   source tree from the archived base and current overlay; compare its hashes
   with every deployed artifact before submission. The generator's local
   [static dry run](tier1-rho-joint-unit-root-dryrun.json) validated both
   manifests and the auditor's frozen-input checks. Its binary
   hash comes from the local macOS correctness build and must be replaced
   with the Linux binary hash before dispatch.
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

## Projective Q table for one restart

The opt-in `--pilot-rho-restart-joint-projective-graph-planned` mode retains
the requested Q seeds as Jacobian points after graph construction. It skips
the batch affine conversion and the per-digit two-X orbit precomputation.
The evaluator rotates a Q point at use time and adds it projectively; G
digits, scalar recoding, the 22 Horner steps, and final output conversion use
the same path as the planned affine Q-table mode. Both modes load the same
frozen graph before their online interval. The source-formula calculation for
the first restart has 21 distinct requested Q seeds, 22 Q additions, and 16
nontrivial Q rotations. On generic nonidentity branches, the projective mode
saves 43 field multiplications and one batch inversion, with one additional
field square. The two tables retain the same byte count for this fixture
because a two-X affine entry and a Jacobian entry each contain three field
elements. Exceptional point branches can change the exact operation count.

The [projective replay receipt](projective-q-local-replay.json) pins the source,
binary, plan, and fixture hashes and records ten exact outputs: both table
representations on the frozen Q and four alternate Q points. The isolated
Tier 1 wall comparison will pair these two modes on the same one-restart
fixture and charged preparation plus evaluation interval. The local replay
establishes correctness and the source-level tradeoff; its elapsed times are
not admitted as wall-performance evidence.

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
