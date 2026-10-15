# Rust BSGS and preprocessing-rho hot paths (2026-10-15)

## Scope and revisions

This engineering pass changes two Rust implementation details on branch
`codex/rust-bsgs-rho-hotpaths`, based on
`fd1ab97cc4a9e3af8750d54c10b73d2b8772e22c`:

- `bsgs_fast::FastField::mul` computes Montgomery REDC with a high-word
  subtraction and one conditional addition. The mathematical result is the
  same residue for the declared odd-modulus bound `p < 2^63`.
- `preprocessing_rho` reads the low byte of a `BigUint` through its digit
  iterator for the per-step partition and distinguished-point tests. It
  retains the existing byte-test behavior for `dp_bits >= 8`.

The input distributions, walk steps, candidate checks, and accounting
intervals are unchanged. This pass does not establish a new ECDLP method.

## Correctness and code generation

The arithmetic identity was checked with Python seed `0x614e` on 20,800
random products over 104 odd moduli, including `3`, `5`, `10007`, and
`2^63 - 1`: the subtraction REDC result equaled
`(a*b*2^-64) mod p` in every case. The Rust regression covers edge operands
and 300 generated pairs for each of three moduli. `rustfmt --check` on the
two changed files and `git diff --check` passed. A release-profile Cargo
unit-test binary ran all 12 `bsgs_fast` tests and all 5 `preprocessing_rho`
tests successfully, including whole-group and interval solve checks and
the new boundary tests. The command that built that binary was:

```sh
cargo test --offline --release --manifest-path suite/Cargo.toml --lib \
  cryptanalysis::bsgs_fast::tests::field_mul_at_word_boundary \
  --target-dir build-rust-perf-base -j4 -- --exact
```

The remaining tests were run from the resulting
`build-rust-perf-base/release/deps/cryptanalysis_suite-5795b8e4300fd04e`
binary with filters `cryptanalysis::bsgs_fast::tests` and
`cryptanalysis::preprocessing_rho::tests`, each with `--test-threads=1`.

With `rustc 1.93.1`, `--edition=2021 -C opt-level=3 --crate-type lib --emit asm`
on Darwin arm64, a standalone function containing the old reduction lowered
to ten arithmetic/conditional instructions before `ret`; the new reduction
lowered to seven. The old path included a low-word product and carry add;
the new path used `subs`, `csel`, and `add` after the high-word products.
The emitted instruction sequences were:

```text
old: umulh mul mul umulh mul cmn adc cmp csel sub
new: mul mneg umulh umulh subs csel add
```

This is a code-generation observation for that standalone function, not an
end-to-end timing result.

## Paired BSGS benchmark

The baseline release `perfbench` build began from the base revision before
the source edit. The source was edited while its compiler was running, so
this exploratory build is not a sealed frozen-source receipt. The binary
was copied before rebuilding the same release target with the changes.
Both builds used the same harness and Rust 1.93.1. The command was:

```sh
python3 scripts/perf/perfindex.py compare \
  --base build-rust-perf-base/perfbench-baseline \
  --cand build-rust-perf-base/release/examples/perfbench \
  --filter dlp/bsgs_fast_toy40_w1_x4 \
  --filter dlp/bsgs_fast_toy40_w4_interval38_x8 \
  --rounds 5 --samples 1 --max-seconds 1 --threads 1 \
  --out build-rust-perf-base/compare-bsgs-rust
```

The [raw comparison receipt](rust-hotpaths-2026-10-15.json) preserves every
arm time, order, fingerprint, and host field. Both kernels kept one matching
fingerprint across all A, B, and A2 invocations. The one-worker kernel had
paired median baseline/candidate ratio `0.775` (95% bootstrap interval
`0.380–1.702`, A/A noise 24.0%); the four-worker interval kernel had ratio
`1.136` (`0.833–1.245`, A/A noise 68.2%). Both verdicts were **neutral**.
The host load average was 65–78 on 14 logical cores. These timings cannot
establish a wall-time gain or exclude a regression. They measure full BSGS
build and target solves; they do not isolate the reducer's own cost.

No paired preprocessing-rho wall-time benchmark was run in this pass; its
allocation removal is established from the code path and the `num-bigint`
digit iterator, while its runtime effect remains unmeasured.

## Remaining checks

Rerun the paired BSGS comparison with frozen builds on an isolated host,
and measure preprocessing-rho
against a fixed workload before claiming wall-time improvement. The broader
request to optimize the repository remains open beyond these two paths.
