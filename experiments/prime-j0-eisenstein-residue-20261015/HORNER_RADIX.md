# Table-light Eisenstein Horner scalar multiplication

The norm-110557 digit recoder can evaluate a secp256k1 scalar with one reusable digit row and one terminal row. The final native pilot retained **2,566,612 bytes** and reproduced all **12,288 distinct frozen scalar points**. Direct table preparation took `249.647051 ms`; the 12,288-point scalar phase took `846.057887 ms`. These are correctness and cost-shape observations from one untiered pilot. The next timing gate is a frozen, same-input Tier 1 comparison of cold preparation plus scalar work and a separate prepared-table online comparison.

## Recurrence and table placement

Let `π = 334−τ`, with `τ² = 3τ−3`. The exact recoder steps give `zᵢ = dᵢ + π zᵢ₊₁` for fifteen digits and a terminal pair `z₁₅`. The point recurrence starts from `z₁₅G` and processes `d₁₄, …, d₀`:

`P ← [334]P − τ(P) + dᵢG`.

Both native tables use base `G`: the 18,427 canonical digit seeds use 96-byte two-x entries, and the terminal seeds use 64-byte affine entries. The final constructor builds these two rows directly. The endomorphism action uses eight doublings, four projective additions, one `τ` evaluation, and one projective subtraction per nonzero Horner stage; the selected digit is added as an affine point. The terminal table is the starting value of the recurrence. The table is independent of the input scalar and remains reusable.

The [hash-guarded overlay](native_alt_horner_overlay.py) modifies the frozen Rust front and window source. It preserves the original recoder and its checked digit and terminal assertions, changes the evaluation schedule, and adds a bounded pilot command. The [native provenance archive](horner-native-provenance.tar.gz), SHA-256 `dee6ba0e999cfd42fa4891cc71a5f7df020fbc7d7ed1a4c690836fcde4bd046c`, preserves three successive binaries and their exact source snapshots. The final front, window source, and binary SHA-256 values are `6cd0962b58b4673708af813a913474791400a7297142e4e5970e7af11faf0b34`, `6b0a9c23f8fbbd846b41da35779ea381e095eeeca2ce050fb5cc65e12249c76c`, and `fd44f97a0201767923098a23a084b2a30ca24ec4a9028ab1e248f25d55adbf02`.

## Exact replay and measured boundaries

The [pilot audit](horner-pilot-audit.json) checks native source, binaries, fixture, point outputs, and the Lean receipt. The first constructor passed 1, 128, and 12,288 distinct points; a direct two-row constructor and the final base-`G` terminal constructor each passed all 12,288 points. The final [stdout receipt](horner-terminal-g-pilot-12288.stdout) reports `verified=1`, `preparation_ms=249.647051`, `online_ms=846.057887`, and `retained_bytes=2566612`. The scalar-phase interval includes the Horner group arithmetic and final affine conversion. The preparation interval includes table generation and accepted-build initialization. Fixture parsing and process launch precede these intervals; the independent point checks follow them.

The first attempt to shorten the existing uniform benchmark with arguments `128 1` reached that command's fixed-fixture assertion and exited 101; its [stderr](horner-invalid-args.stderr) is preserved. The bounded `--pilot-alt-horner` entry point then verified the requested prefix lengths. These timings have no Tier 1 isolation or paired A/A controls, so they are diagnostics and do not rank the new path against the prepared 27,429,548-byte table.

## Formal proof map

The pinned toolchain is `leanprover/lean4:v4.34.1`. Run `python3 check_horner_lean.py` to build `AlternateRadix.lean` into a fresh temporary olean and check [HornerRadix.lean](HornerRadix.lean). The [proof receipt](horner-lean-check.json) records both source hashes, commands, outputs, and `#print axioms`; all three new theorems report only `propext`. `lean4checker --fresh` was unavailable in this environment.

| Mathematical obligation | Lean declaration | Status |
| --- | --- | --- |
| Exact quotient by `334−τ` and fifteen-step terminal bound | `AlternateRadix.quotient_step`, `terminal_from_verified_digit_steps` | Checked under their explicit recoder hypotheses |
| A chain of exact quotient equations equals pair Horner evaluation | `HornerRadix.valid_trace_evaluates` | Checked for every finite digit list and terminal pair |
| Pair evaluation commutes with point Horner evaluation | `HornerRadix.map_evaluatePairs` | Checked under explicit addition- and prime-preservation hypotheses |
| Initial pair evaluates to the Horner point | `HornerRadix.point_horner_of_valid_trace` | Checked under exact trace and point-map hypotheses |
| The concrete secp256k1 implementation satisfies the point-map and trace hypotheses | — | Open; native exact replay covers the frozen 12,288-point fixture |

The point-map bridge requires the concrete `τ` implementation to be additive and to satisfy `τ²=3τ−3` on the declared subgroup, and requires the Rust recoder's emitted sequence to form the Lean `ValidTrace`. Those are the precise remaining formalization obligations. A matched Tier 1 panel must charge cold preparation and prepared-table scalar work separately before selecting this low-memory route for a workload.
