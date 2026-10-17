# Table-light Eisenstein Horner scalar multiplication

The norm-110557 digit recoder can evaluate a secp256k1 scalar with one reusable digit row and one terminal row. The final native pilot retained **2,566,612 bytes** and reproduced all **12,288 distinct frozen scalar points**. In a matched Tier 1 single-scalar cold-start panel, its mean preparation plus scalar time was **252.74 ms**, versus **3217.75 ms** for the 27,429,548-byte full two-x prefetch path. The paired median reference/Horner cold ratio was **12.75×** across 16 verified comparisons. A separate matched prepared-table panel measured **8385.59 ms** for Horner versus **565.41 ms** for full prefetch over 122,880 checked outputs per arm. Thus the table-light path buys a large single-scalar setup advantage and 90.6% less retained table memory at a measured **14.8× prepared-table throughput cost** in this implementation.

## Recurrence and table placement

Let `π = 334−τ`, with `τ² = 3τ−3`. The exact recoder steps give `zᵢ = dᵢ + π zᵢ₊₁` for fifteen digits and a terminal pair `z₁₅`. The point recurrence starts from `z₁₅G` and processes `d₁₄, …, d₀`:

`P ← [334]P − τ(P) + dᵢG`.

Both native tables use base `G`: the 18,427 canonical digit seeds use 96-byte two-x entries, and the terminal seeds use 64-byte affine entries. The final constructor builds these two rows directly. The endomorphism action uses eight doublings, four projective additions, one `τ` evaluation, and one projective subtraction per nonzero Horner stage; the selected digit is added as an affine point. The terminal table is the starting value of the recurrence. The table is independent of the input scalar and remains reusable.

The [hash-guarded overlay](native_alt_horner_overlay.py) modifies the frozen Rust front and window source. It preserves the original recoder and its checked digit and terminal assertions, changes the evaluation schedule, and adds a bounded pilot command. The [native provenance archive](horner-native-provenance.tar.gz), SHA-256 `dee6ba0e999cfd42fa4891cc71a5f7df020fbc7d7ed1a4c690836fcde4bd046c`, preserves three successive binaries and their exact source snapshots. The final front, window source, and binary SHA-256 values are `6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34`, `6b0a9c23f8fbbd846b41da35779ea381e095eeeca2ce050fb5cc65e12249c76c`, and `fd44f97a0201767923098a23a084b2a30ca24ec4a9028ab1e248f25d55adbf02`.

## Exact replay and measured boundaries

The [pilot audit](horner-pilot-audit.json) checks native source, binaries, fixture, point outputs, and the Lean receipt. The first constructor passed 1, 128, and 12,288 distinct points; a direct two-row constructor and the final base-`G` terminal constructor each passed all 12,288 points. The final [stdout receipt](horner-terminal-g-pilot-12288.stdout) reports `verified=1`, `preparation_ms=249.647051`, `online_ms=846.057887`, and `retained_bytes=2566612`. The scalar-phase interval includes the Horner group arithmetic and final affine conversion. The preparation interval includes table generation and accepted-build initialization. Fixture parsing and process launch precede these intervals; the independent point checks follow them.

The first attempt to shorten the existing uniform benchmark with arguments `128 1` reached that command's fixed-fixture assertion and exited 101; its [stderr](horner-invalid-args.stderr) is preserved. The bounded `--pilot-alt-horner` entry point then verified the requested prefix lengths. These timings have no Tier 1 isolation or paired A/A controls, so they are diagnostics and do not rank the new path against the prepared 27,429,548-byte table.

## Matched Tier 1 cold-start panel

The [manifest](tier1-horner-cold-cpu40-manifest.json), [acceptance rules](tier1-horner-cold-cpu40-rules.json), and [launch receipt](tier1-horner-cold-launch.json) were frozen before job `ab1de3ef68f44f12bfa0c56f81b67121` entered the RunPod serial worker. The [hash-guarded reference adapter](native_horner_cold_panel_overlay.py) adds a one-scalar pilot to the existing full two-x prefetch source. Both arms use the first scalar in the same SHAKE256 fixture, `8b0040cf2f698515cf9a3882de34f01c34bc772dbf003d2b8984ad92875d036c`, and independently check the same secp256k1 point after timing. Each invocation starts a fresh process and table. Rust `Instant` measures table preparation and one scalar multiplication separately; fixture parsing, process launch, and exact point verification are outside those intervals. The cold cost for each arm is their sum, and the ratio is formed within each repeat. CPU 40, the exposed NUMA topology, cgroup counters, frequency readback, affinity, noise gates, and source hashes are in the [raw job archive](horner-cold-tier1-raw.tar.gz). This is a cloud-instance Tier 1 measurement; the pod does not establish physical-host exclusivity.

| Variant | Retained table | Mean preparation plus scalar, 16 comparison arms | Mean scalar phase, descriptive |
| --- | ---: | ---: | ---: |
| Full two-x prefetch | 27,429,548 bytes | 3217.75 ms | 0.0532 ms |
| Eisenstein Horner | 2,566,612 bytes | 252.74 ms | 0.0892 ms |

The paired median cold ratio is `12.7521`, with the predeclared 95% bootstrap interval `[12.6767, 12.7854]`. All 96 arms and 48 pairs were valid, the artifacts were stable, and both A/A controls passed on every repeat. The scalar-only intervals are too short for the cold A/A gate to validate a separate online speed claim; their means describe the cost tradeoff only. The runner's generic `paired_speedup` field uses `online_ms` and is not the cold metric. The [independent auditor](analyze_tier1_horner_cold.py) recomputes the cold totals from every raw stdout, checks the fixture's first scalar and point, source/binary hashes against the [native provenance archive](horner-cold-native-provenance.tar.gz), runner status, all noise receipts, A/A bounds, and the bootstrap gate. Its [receipt](tier1-horner-cold-cpu40-audit.json) records the raw archive SHA-256 `d872018620ad53581bf64de2ae24ac3c9d28493d72e75906b8bbadb672df27c8` and native archive SHA-256 `1ab0ec216b143038b7f261bc49af7197e4434f0ef9c301b73ef2ee97d70c153e`.

## Matched Tier 1 prepared-table online panel

The [online manifest](tier1-horner-online-cpu40-manifest.json), [rules](tier1-horner-online-cpu40-rules.json), and [launch receipt](tier1-horner-online-launch.json) were frozen before serial job `fea3a512d7e245e5ab43a957b90e349a`. Both existing binaries executed ten passes over the same 96 frozen batches of 128 distinct SHAKE256-derived scalars. Each arm checked all **122,880** outputs after Rust `Instant` stopped. The timed interval includes batch scalar multiplication and affine conversion; table preparation, fixture loading, process launch, and output verification are outside it. The panel paired full two-x prefetch against Horner within each of 16 repeats, surrounded by prefetch/prefetch A/A cases on CPU 40.

| Prepared-table implementation | Retained table | Mean online time per 122,880 outputs | Paired reference/Horner median |
| --- | ---: | ---: | ---: |
| Full two-x prefetch | 27,429,548 bytes | 565.41 ms | — |
| Eisenstein Horner | 2,566,612 bytes | 8385.59 ms | 0.06752 |

The paired reference/Horner ratio has a predeclared 95% bootstrap interval `[0.06693, 0.06781]`, equivalent to Horner taking about **14.8 times** as long for this prepared-table workload. All 96 arms and 48 pairs were valid; every repeat's two A/A ratios fell in `[0.90, 1.11]`; artifact hashes stayed stable. The [independent online auditor](analyze_tier1_horner_online.py) checks every raw stdout and noise status against the frozen manifest, plus source/binary hashes in the [native provenance archive](horner-online-native-provenance.tar.gz). Its [receipt](tier1-horner-online-cpu40-audit.json) records the [raw archive](horner-online-tier1-raw.tar.gz) SHA-256 `bf73541515cb0261e687ccf5e17e92a0f1dc7592015564bb6fb542447ca7abac` and native archive SHA-256 `7bfb1c8b959cd87b89a7acfa80afe57bb49ff0aa135406d75f6b657729515f04`. Both panels are Tier 1 cloud-instance measurements and use different frozen workloads; their times are separate workload results, not interchangeable per-scalar estimates.

## Formal proof map

The pinned toolchain is `leanprover/lean4:v4.34.1`. Run `python3 check_horner_lean.py` to build `AlternateRadix.lean` into a fresh temporary olean and check [HornerRadix.lean](HornerRadix.lean). The [proof receipt](horner-lean-check.json) records both source hashes, commands, outputs, and `#print axioms`; all three new theorems report only `propext`. `lean4checker --fresh` was unavailable in this environment.

| Mathematical obligation | Lean declaration | Status |
| --- | --- | --- |
| Exact quotient by `334−τ` and fifteen-step terminal bound | `AlternateRadix.quotient_step`, `terminal_from_verified_digit_steps` | Checked under their explicit recoder hypotheses |
| A chain of exact quotient equations equals pair Horner evaluation | `HornerRadix.valid_trace_evaluates` | Checked for every finite digit list and terminal pair |
| Pair evaluation commutes with point Horner evaluation | `HornerRadix.map_evaluatePairs` | Checked under explicit addition- and prime-preservation hypotheses |
| Initial pair evaluates to the Horner point | `HornerRadix.point_horner_of_valid_trace` | Checked under exact trace and point-map hypotheses |
| The concrete secp256k1 implementation satisfies the point-map and trace hypotheses | — | Open; native exact replay covers the frozen 12,288-point fixture |

The point-map bridge requires the concrete `τ` implementation to be additive and to satisfy `τ²=3τ−3` on the declared subgroup, and requires the Rust recoder's emitted sequence to form the Lean `ValidTrace`. Those are the precise remaining formalization obligations. The measured cold and prepared-table endpoints now motivate an intermediate schedule that spends table memory on selected powers of `π` and evaluates the remaining powers at runtime; its exact algebraic recurrence, memory accounting, and point replay are the next design gates.
