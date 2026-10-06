# A curve-generic index-calculus engine: audit and design

This document consolidates a full audit of every index-calculus (IC) code
path in the `crypto` and `cryptanalysis` repositories, and specifies the
`icx` engine and CLI built on top of it: one command that accepts **any
standardized elliptic curve by name** — prime, binary (random and Koblitz),
extension-field, and characteristic-three — verifies it, estimates its IC
cost against the generic-attack boundary, and runs the pluggable pipeline at
whatever parameters are feasible, with CADO-NFS-style staged progress and an
ETA, across x86-64, aarch64, and Apple silicon, with optional CUDA/Metal
offload.

It is written to this repository's reporting convention (`AGENTS.md`): every
claim is scoped, every cost is a ratio to a boundary, and *extrapolation is
labelled as extrapolation*. Nothing here claims to break a curve.

## 1. Honest scope (read this first)

Index calculus is only sub-exponential on some ECDLP instances:

- **Prime-field curves** (P-256, secp256k1, Brainpool, …): no sub-exponential
  IC is known. Pollard rho is the best attack. The engine will *run* an IC
  pipeline on a scaled-down prime curve for study, and *estimate* the real
  curve, but IC is not a threat here and the CLI says so per curve.
- **Binary and Koblitz curves** over `F_{2^n}`, and curves over extension
  fields `F_{p^k}` with `k ≥ 3`: Weil-descent / summation-polynomial IC is
  the relevant sub-exponential attack (Semaev, Gaudry, Diem, FGHR, GGMP).
  This is where the interesting crossovers live, and where this repository
  already has measured end-to-end results (largest solved: a 48-bit subgroup
  of `K_0/F_{2^61}`).
- **Characteristic-three** curves (pairing-era supersingular curves over
  `F_{3^m}`): included for completeness of coverage; IC via descent applies
  in principle at descent-feasible sizes only.

Consequently the CLI classifies every curve into one of three **run regimes**,
and never conflates them:

| regime | meaning | what a run produces |
|---|---|---|
| `attack` | IC is the relevant sub-exponential attack AND the instance is within the demonstrated end-to-end envelope | a verified logarithm, cost as `S = ops/√r` with a ratio to rho |
| `scaled` | the named curve is out of envelope; the run executes on a same-family analogue at feasible size | a verified logarithm on the analogue + a labelled extrapolation to the named curve |
| `estimate` | no feasible run (e.g. P-521); closed-form floors and fitted exponents only | a cost estimate with its heuristics stated, no solve claimed |

"You can run `icx` against every standardized curve" is the completion
criterion, and it is met by producing the *correct* one of these three
outputs for each curve — not by pretending to solve what cannot be solved.

## 2. What already exists (audit consolidation)

Five parallel audits covered: the pluggable framework + `ic` CLI; the
polynomial-system solvers; curve/field arithmetic + point decomposition; the C
`cryptanalysis` library; and the GPU/SIMD/CI infrastructure. Findings with
file references live in `docs/ic/` history and the PR description; the load-
bearing facts:

### 2.1 A pluggable IC pipeline already exists (`src/cryptanalysis/ic_framework/`)

The framework turns the boundary ledger inside out: each stage is a plug
point, driven through `ic bench`. Stage traits: `FactorBaseBuilder`,
`DecompositionOracle`, `SystemSolver`, and `RelationSolver` (relation matrix),
over the `CountedGroup` interface. Registered plugins today:

- factor bases: `prime-abscissa`, `binary-subspace`, `koblitz-orbit`
- decomposition oracles: `subtract`, `mitm`, `mitm-frobenius`, `descent-algebraic`
- solvers: `f4-f2`, `buchberger-f2`, `matrix-f4`, `matrix-f5`, `inherited-f4`,
  `crossbred-f2`, `xl-f2`, `sat-cdcl`, `fes-f2`, `fes-f2-wide`, `exhaustive`
- relation matrices: `incremental-gauss`, `structured-gauss`

**So F4, F5, XL, FES (Gray-code), crossbred, and SAT/WDSat are already
implemented and selectable by name.** The gaps are elsewhere.

Solver fidelity (from the solver audit): `pq_f4_f2` is a real F4
(Gebauer–Möller); `mq_fes` is a genuine libfes-lite Gray-code enumerator with
AVX2/AVX-512 kernels; `crossbred` is genuine Joux–Vitse (d=1); `sat.rs` is a
real CDCL with XOR reasoning. `groebner_f4` is actually Buchberger;
`matrix-f4`/`matrix-f5` are Macaulay/XL + DPLL, and `matrix-f5` has no
signatures; `pq_xl` is a toy. `f4_fp` is a real degree-bounded F4 over
`F_p, p<2^32`.

### 2.2 Arithmetic already reaches every standard size

- `F_p`: generic `BigUint` field (`src/ecc/field.rs`), tested to P-521;
  constant-time 256-bit Montgomery for secp256k1/P-256; a reusable generic
  `MontgomeryContext<LIMBS>` exists but is RSA-only today.
- `F_{2^m}`: polynomial-basis `F2mElement` (`src/binary_ecc/f2m.rs`), inline to
  `m ≤ 576`, tested to `m = 1031`, with **runtime PCLMUL (x86) / PMULL
  (aarch64)** multiply and word-level clmul reduction. `IrreduciblePoly` is
  open, so any trinomial/pentanomial builds.
- **The blocker is not representation — it is that every IC *solving* path is
  single-word**: `Gf2` and `pack_point` cap at `n ≤ 62/63`, boolean systems at
  64 variables, relation moduli at `r < 2^63`, and prime relation-finding at
  `p < 2^20` (`find_roots_fp` returns `[]` above that).

### 2.3 A verified curve catalog exists but is not wired to IC

`src/ecc/curve_zoo.rs` (31 prime curves, all verified on-curve and `n·G = O`),
`src/ecc/curve.rs` (secp256k1, P-256, SM2, GOST), and
`src/binary_ecc/curve.rs` (sect113/131/163 families, Oakley Group 3). The `ic`
binary knows only four names and treats them as **inspection-only**
(`imported_target_solving: false`). There is no name→run path.

### 2.4 Hardware infrastructure to reuse

- Runtime SIMD dispatch patterns: the `wide_kernel!` macro (`mq_fes.rs`,
  AVX2/AVX-512), `Simd512` (`koblitz_fast.rs`, AVX-512 + VPCLMULQDQ), and the
  `F2mElement` PCLMUL/PMULL paths.
- The C `cryptanalysis` repo has a **dual-compile CUDA/host-emulator vtable**
  (`cuda/ca_device.cuh`, `src/gpu_internal.h`), a **Metal source generator**
  (`ecc2k130/scripts/mslgen.py`, runtime `newLibraryWithSource`), and a
  bitslice header selecting AVX-512/AVX2/NEON/CUDA lanes.
- CI: `cryptanalysis` already runs on `ubuntu-24.04-arm` and macOS; `crypto`
  runs IC on x86-64 only and only smoke-tests `--help` on macOS.

### 2.5 Confirmed defects

Reproduced by the audits.  **Fixed here, each with a regression test:**

1. `MPoly::mul` dropped the constant term whenever any term cancelled
   (`symmetrized_semaev.rs`) — e.g. `(1+x)(1-x)` came out `-x²`; fixed, the
   final zero-cleanup already handled cancellation.
2. GOST `tc26-256-paramSetA` cofactor recorded as 1; corrected to 4
   (`curve_zoo.rs`) — the catalog Hasse check is the regression test.
3. `Gf2` had no aarch64 carry-less path (perf cliff on Apple silicon /
   Graviton); added the PMULL path (`semaev_decomp.rs`), verified against an
   independent reference.

**Documented, not yet fixed** (they touch heavily-CI'd core Koblitz paths and
are out of scope for this engine PR; each has a proposed fix in the audit):

4. Oakley Group 3 records `#E` as the group order (its generator has order
   `4·q`); the catalog labels it a subgroup curve and verifies `[#E]G = O`.
5. `fes-f2`/`fes-f2-wide` return 1 solution for the empty system (a caller
   cannot know `n` from an empty equation slice; the practical IC path never
   produces an empty system).
6. `pack_point` key collision at `n = 63` (the pipeline runs `n ≤ 62`).
7. `buchberger-f2` panics at `n = 25..26` (wrapper cap above the solver's).

## 3. Design of the `icx` engine

The engine is new code in `crypto_lib` plus a new binary; it **reuses** the
framework, solvers, and arithmetic above rather than reinventing them, and
never destabilizes the existing, heavily-tested `ic` binary or its research
contract.

```
        ┌────────────────────────── icx (new binary) ──────────────────────────┐
        │  list · inspect · estimate · run · plan · bench-curve                  │
        └───────────────────────────────┬───────────────────────────────────────┘
                                         │
        ┌──── curve_catalog ────┐  ┌──── ic_progress ────┐  ┌──── ic_engine ────┐
        │ every std curve, by   │  │ CADO-style staged   │  │ regime classifier │
        │ family+field, verified│  │ log, rate, %, ETA,  │  │ boundary estimate  │
        │ on load               │  │ JSON events         │  │ analogue selection │
        └───────────┬───────────┘  └─────────────────────┘  └─────────┬─────────┘
                    │                                                   │
        ┌───────────┴───────────────── reused ──────────────────────────┴──────┐
        │ ecc::field/curve (F_p BigUint) · binary_ecc::f2m/curve (F_2^m)         │
        │ gf3m (new: F_3^m) · fpk (new: generic F_p^k)                           │
        │ ic_framework (stages, 11 solvers) · ic_boundary (floors, rho ref)      │
        │ field-mul dispatch: PCLMUL/VPCLMUL · PMULL · portable  (+CUDA/Metal)   │
        └───────────────────────────────────────────────────────────────────────┘
```

### 3.1 Curve catalog (`src/cryptanalysis/curve_catalog.rs`)

A single registry keyed by canonical name (with aliases), each entry a
`CatalogCurve` carrying: `family` (`Prime | BinaryRandom | Koblitz | Extension
| Char3`), a `FieldSpec`, the curve coefficients, generator, subgroup order
`n`, cofactor `h`, `#E`, provenance (standard + citation), and a
`security_bits` estimate. Prime and binary entries reuse the existing verified
constructors; the missing standardized curves are added:

- binary: sect193r1/r2, sect233k1/r1, sect239k1, sect283k1/r1, sect409k1/r1,
  sect571k1/r1, Oakley Group 4 (`F_{2^185}`), X9.62 c2tnb/c2pnb families
- extension: study curves over `F_{p^3}`, `F_{p^4}` (Gaudry/Diem regime)
- char-3: ηT-pairing supersingular curves over `F_{3^m}`, `m ∈ {97,163,193,
  239,353,509}` (Boneh–Lynn–Shacham / ηT literature), clearly labelled

Every entry is **verified when it is constructed** (generator on curve,
`n·G = O`, `h·n` within the Hasse interval), by a table-driven test that
asserts a per-family floor plus per-family coverage — never an exact global
count (per the `CLAUDE.md` corpus-count rule).

### 3.2 Field arithmetic and the missing fields

- Reuse `F_p` (BigUint) and `F_{2^m}` as-is.
- Add `gf3m`: `F_{3^m}` in polynomial basis over `F_3`, packed two bits per
  trit with the standard base-3 add/mul, tested against a schoolbook oracle.
- Add `fpk`: generic `F_{p^k}` over a BigUint base field with an arbitrary
  irreducible, for the extension-field descent regime.
- **Field-multiply dispatch** (`src/cryptanalysis/field_dispatch.rs`): one
  entry point choosing at runtime among VPCLMULQDQ/PCLMUL (x86-64), PMULL
  (aarch64, incl. Apple M-series), and a portable fallback; the chosen backend
  is recorded in every report. This closes the `Gf2` aarch64 gap.

### 3.3 Progress + ETA (`src/cryptanalysis/ic_progress.rs`)

A reusable reporter modelled on CADO-NFS. Emits, to stderr in human mode and
as JSON lines under `--json-progress`:

```
Info:Factor base: 296 columns, 36112 signed points built in 0.4s
Info:Relation collection: 140/296 cols  (47.3%)  312 rel/s  ETA 0:00:21
Info:Linear algebra: structured Gauss, 296x312, rank 295 ... 0.03s
Info:Descent: target 7/32 verified (0.05s)
Info:Total: recovered log, S=1.9e6/sqrt(r)=... , 1.17x rho
```

ETA is `remaining_work / observed_rate` where `remaining_work` combines the
observed relation rate with the expected number of relations still needed
(from columns remaining and the measured hit rate); it is shown as a range
once the rate estimate stabilizes, and marked provisional before then.

### 3.4 The engine and CLI

`icx <curve>` inspects; subcommands:

- `icx list [--family F]` — every catalog curve, its field, regime, security.
- `icx inspect <curve>` — full parameter verification (reuses `params.rs`
  checks, generalized past the 512-bit cap).
- `icx estimate <curve> [--solver ...]` — boundary floors, family-optimum `S`,
  fitted-exponent extrapolation; no solve.
- `icx run <curve> [--factor-base ...] [--oracle ...] [--solver ...]
  [--linalg ...] [--regime auto|scaled|attack]` — runs the pipeline via the
  framework at the feasible size, prints staged progress + ETA, verifies the
  recovered logarithm, and reports `S` and the ratio to rho, with the regime
  labelled.
- `icx plan <curve>` — the analogue ladder and expected costs for a `scaled`
  run, without running.

All subcommands support `--json` for a machine-readable report carrying the
provenance block (binary hash, git commit, host, dispatched backend).

### 3.5 GPU/Metal offload

The embarrassingly-parallel stages are FES Gray-code enumeration and batch
relation search. Both get optional backends behind cargo features
(`cuda`, `metal`), each with a **CPU cross-check** run in CI so correctness is
tested without a device (reusing the dual-compile/emulator pattern). The
scalar/AVX path remains the default and the source of truth.

## 4. CI

A new matrix workflow builds and tests `icx` on `ubuntu-latest` (x86-64),
`ubuntu-24.04-arm` (aarch64), and `macos-14` (Apple silicon), runs `icx list`
and `icx inspect`/`icx estimate` across the **whole catalog**, and runs `icx
run` on the in-envelope curves. Separate jobs compile-check the CUDA and Metal
backends (macOS for Metal). The correctness gate is the verified-logarithm and
counter checks, which are host-independent.

## 5. Sequencing

1. catalog + field verification + `icx list/inspect` + CI skeleton (this PR's
   first push, so CI runs immediately);
2. `ic_progress` + `icx estimate` (boundary reuse);
3. `icx run` wired to the framework with regime classification;
4. `gf3m` + `fpk` and their curves;
5. field-dispatch + `Gf2` aarch64 path;
6. CUDA/Metal FES backends + cross-checks;
7. confirmed-bug fixes with regression tests;
8. drive CI green across all three architectures.

Each step lands compiling and tested; nothing is stubbed-and-claimed.
