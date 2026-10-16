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
cases. The one-restart panel runs 28 cases and the 128-restart panel runs 24;
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
| `compare_cost_aware` (one restart) | OpenSSL no-warmup | Cost-aware Q graph and shared Horner |
| `compare_cost_aware_vs_unit_root` (one restart) | Unit-root graph | Cost-aware graph, same scalar stream and Q |
| `compare_projective` (one restart) | OpenSSL no-warmup | Projective Q table from the cost-aware graph |
| `compare_projective_vs_affine` (one restart) | Affine Q table from the cost-aware graph | Projective Q table from the same graph |
| `compare_mixed_cost` (128 restarts) | OpenSSL no-warmup | Cost-aware mixed-addition graph and shared Horner |
| `compare_mixed_cost_vs_weighted` (128 restarts) | Low-rotation graph | Cost-aware mixed-addition graph, same scalar stream and Q |
| `compare_hybrid` (128 restarts) | OpenSSL no-warmup | Reuse-selective Q table from the cost-aware graph |
| `compare_hybrid_vs_affine` (128 restarts) | Affine Q table from the cost-aware graph | Reuse-selective Q table from the same graph |
| `compare_triple81` | OpenSSL no-warmup | Norm-6481 tripling Horner with its frozen-scalar seed graph |
| `compare_triple81_vs_cost_aware` (one restart) | Affine Q table from the cost-aware graph | Norm-6481 tripling Horner on the same Q and scalar pair |
| `compare_triple81_vs_mixed_cost` (128 restarts) | Affine Q table from the mixed-cost graph | Norm-6481 tripling Horner on the same Q and scalar stream |
| `cal_mid` | OpenSSL no-warmup | OpenSSL no-warmup |
| `compare_fused` | OpenSSL no-warmup | Sparse Q table, batched affine pair sums, shared Horner, batched output normalization |
| `compare_fused_graph` | OpenSSL no-warmup | Shared Q-seed graph followed by batched affine pair sums and output normalization |
| `compare_fused_graph_planned` | OpenSSL no-warmup | Precompiled scalar graph followed by batched pair sums and output normalization |
| `cal_after` | OpenSSL no-warmup | OpenSSL no-warmup |

All candidate commands time affine serialization. OpenSSL's interval starts at
its first `EC_POINT_mul` for the public `a,b,Q` and includes every requested
restart. Its Q parsing and curve construction precede the timer. The joint
commands exclude globally reusable G and canonical-seed preparation; their
`online_ms` includes Q parsing, table construction, restart evaluation, and
affine output. The older joint arms also charge a-scalar recoding, and their
direct and online graph modes charge b-scalar recoding. The triple81 arm
compiles both frozen scalar streams before its target timer and reports that
preparation separately. The planned graph arms load separately frozen
artifact of b-scalar choices and graph topology. The artifact contains no Q
and is hashed in the panel manifest. They report `plan_load_ms` and
`plan_bytes`, and charge graph instantiation on Q online. The hybrid mode
also compiles its repeated-seed selector from those frozen choices during
plan load, before the target timer, and includes the selector in `plan_bytes`.
The triple81 arm compiles its own Q-independent radix choices and seed graph
and prepares G before target timing; it reports the graph's retained bytes
and preparation interval separately.
The auditor preserves
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

The one-restart panel has 448 planned pairs and 896 arms; the 128-restart
panel has 384 pairs and 768 arms. Each includes 48 OpenSSL A/A control pairs.
The queue runs one subprocess at a time on CPU 40. The Tier 1
receipt must retain exposed topology, affinity, cgroup limits, throttling,
steal time, memory and calibration noise. A comparison advances only when
all 16 pairs for that case are valid, the bracketing A/A controls lie within
`[0.90,1.11]`, the paired bootstrap 95% log-ratio interval excludes one,
and every point independently replays. A failed or noisy arm stays in the
ledger and leaves the corresponding aggregate unknown.

## Build, freeze, and dispatch sequence

1. After the source-transfer approval, copy the approved overlay, joint
   module, rho command module, archived Cargo/base source, the
   hash-checked `ct_bignum.rs`, and the
   [compile fixture archive](mixed640-compile-fixtures-20261016.tar.gz)
   to the existing Pod. Extract its three `mixed640_*_fixture.json` members
   into `src/bin/` before compilation; their exact bytes are required by
   `include_str!` even though the joint benchmark does not execute those
   modes. The archive SHA-256 is
   `378c611a5204abcfa1bcf819a73ca1ec3f0e5c1f335637a509125e5a9d021baa`.
   Apply the
   [hash-guarded overlay](native_rho_restart_joint_overlay.py) to a fresh copy
   of the archived hybrid source, passing the `ct_bignum.rs` path as its
   second argument. The overlay replaces the archived macOS absolute module
   path with `eisenstein_fixed/ct_bignum.rs` and copies the checked source
   into that relative location. Build the x86-64 release binary offline;
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
   [prior static dry run](tier1-rho-joint-hybrid-dryrun.json) validated both
   manifests and the auditor's frozen-input checks before selector compilation
   moved into plan load. Regenerate the manifests and repeat that check for
   the current source. Replace the local macOS binary hash with the Linux
   binary hash before dispatch.
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
Tier 1 panel pairs these two modes on the same one-restart fixture and charged
preparation plus evaluation interval. The [panel dry run](tier1-rho-joint-projective-dryrun.json)
validates the frozen command order and independent auditor through the raw
archive boundary. The local replay
establishes correctness and the source-level tradeoff; its elapsed times are
not admitted as wall-performance evidence.

## Reuse-selective Q table for 128 restarts

The opt-in `--pilot-rho-restart-joint-hybrid-graph-planned` mode compiles the
use count of each Q seed from the frozen scalar plan before target timing.
It batch-normalizes seeds used at least
twice and retains single-use seeds projectively. For a digit used `u` times
with `r` nontrivial unit rotations, affine storage pays `7M + 1S` in table
preparation and saves `4uM + uS + rM` at use sites on generic branches.
Thus a repeated digit dominates projective storage in both multiplications
and squares, while a single-use digit is cheaper projectively. The batch
inversion remains shared by the repeated digits. This is a source-formula
selection rule; it does not predict cache or branch costs. The pinned Lean
theorems `JointSeedGraph.repeated_digit_affine_dominates` and
`JointSeedGraph.singleton_digit_projective_dominates` prove these generic
cost inequalities under their stated use and rotation hypotheses; the
[proof check](joint-seed-graph-lean-check.json) records the build and axioms.

The frozen 128-restart stream uses 659 distinct Q digits: 614 repeated and
45 singletons. The singleton choices contain 30 nontrivial rotations. The
hybrid table saves 105 modeled multiplications over the all-affine table,
with the same modeled square count and one shared inversion. Its tagged
entries retain more memory than the uniform affine table, so the Tier 1
wall comparison must measure the complete preparation and evaluation path.
The [hybrid replay receipt](hybrid-q-local-replay.json) records 266 exact
outputs: both table modes across the 128 frozen restarts, the frozen first
restart, and four alternate Q points. The 128-restart comparison is a batch
question separate from the primary one-restart panel.

After moving selector compilation into plan load, a macOS ARM64 release build
with SHA-256 `e36ead44e3ba6cc5102a304bef29372ed0944d1c2f17acb56514cdec42c372da`
replayed the frozen 1- and 128-restart plans in both affine and hybrid modes.
All four commands reported `verified=1` and the same expected final point for
each count. The hybrid selector retained 48 and 4,128 additional plan bytes,
respectively; the 128-restart table still selected 614 affine and 45
projective Q seeds. These commands check the changed accounting path and
exact output. Their local elapsed times are outside the Tier 1 wall gate.

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

## Norm-6481 tripling Horner candidate

The opt-in `--pilot-rho-restart-joint-triple81` path evaluates `aG+bQ` in the
Eisenstein radix `81+omega = 82-tau`. Its conjugate is `79+tau`, and their
product is `6481`. A quotient step subtracts a shortest digit with the same
residue modulo `6481`, then multiplies the coefficient pair by the conjugate
and divides both coordinates exactly by `6481`. Twenty fixed steps leave a
terminal pair of norm at most `3` across the frozen 128-restart fixture.
The sixfold unit orbit folds requested digit coefficients into a graph of Q
seeds. The scalar stream and graph are compiled before target timing; online
work instantiates the graph on Q, batch-normalizes its requested points,
applies the shared Horner recurrence, and serializes every output.

The Horner step computes `81P+omega(P)` as four applications of the paper's
Jacobian tripling formula, one unit rotation, and one projective addition.
The tripling formula uses `4S+6M`; the current native backend implements a
square through the same Montgomery routine as a multiplication. For the
frozen one-restart stream, 20 steps therefore use 80 triplings, or
`320S+480M`, in the repeated scalar operator. The norm-4033 step uses 22
steps of six doublings, or 132 doublings. The native doubling source uses
`5S+2M`, giving `660S+264M` for that operator. Digit additions, Q-table
construction, rotations, exceptional branches, and output conversion remain
separate costs; the complete candidate is subject to the same Tier 1 paired
wall gate as the current arms.

The macOS ARM64 release binary with SHA-256
`105a36cc67330c810f271d4523fbb8c0961c57de1f4d4298382b0ab56b6fd372`
verified 393 exact outputs: the frozen first and first 128 restart points;
one restart each for independently constructed `Q=G`, `Q=2G`, and `Q=5G`;
128 restarts for `Q=2G`; 128 fresh seeded `(a,b)` pairs with `Q=2G`; and five
edge cases including the identity result. The alternate expected points were generated
from each public `(a,b)` as `(a+bq)G` by the installed `cryptography` secp256k1
backend. The fresh panel draws 128 independent nonzero `a,b` values with
Python's `random.Random(0x648120261016)` and orders each from
`[1, r-1]`, where `r` is the secp256k1 subgroup order. The edge pairs are
`(0,0)`, `(1,0)`, `(0,1)`, `(r-2,1)`, and `(r-1,r-1)`.
The seeded and edge fixture SHA-256 values are
`22b74bf09006b3bfedf5ada7fe241e8d030a6be4c07bc6dc556dea9ffcfcec78`
and `a23d0cc09c09b1de9d8a635af2e4326cbe4698024112879e92ec35e898e1a81e`.
The frozen one-restart Q graph has 13 edges and eight direct seeds;
the 128-restart graph has 973 edges and one direct seed. The respective
retained graph plans are 2,820 and 136,390 bytes; the batch asks a distinct
table-amortization question.

The pinned [Lean module](Triple81Radix.lean) proves the conjugate product,
exact quotient-step implication, recoder trace reconstruction, and shared
two-scalar Horner theorem with explicit point-addition and radix-map premises.
It also proves that 20 exact quotient steps put the terminal pair below norm
`5000` when the initial norm is at most `7*2^260` and each selected digit
has norm at most `6481`. The proof map is
`prime_norm81` for the radix norm, `quotient_norm_step` for each contraction,
`twenty_step_terminal_bound` for the numeric recurrence, and
`twenty_quotients_terminal` for the pair-sequence implication. The
[native replay verifier](verify_triple81_native.py) independently enumerates
all 3,240 nonzero positive residue classes, checks the Rust selector's search
rule against a complete bounded lattice search, and records a maximum digit
norm of `2107`. Sign symmetry and the zero digit cover all 6,481 residue
classes. The coordinate box is complete because
`4Q(a,b)=a²+3(a+2b)²=(2a+3b)²+3b²`; any coordinate outside `[-150,150]`
has norm above `2107`. A Lean refinement of that concrete selector and the
Jacobian operation remain formalization obligations; the frozen and
alternate point replays check the implemented path.
The [pinned proof receipt](joint-seed-graph-lean-check.json),
[native replay receipt](triple81-local-replay.json), and
[Tier 1 static audit](tier1-rho-joint-triple81-dryrun.json) retain the
commands, hashes, and verification status.
Reproduce the native checks with the
flag above and counts `1` and `128` on the frozen fixture. Local elapsed
times from these correctness commands are not used as Tier 1 comparisons.
