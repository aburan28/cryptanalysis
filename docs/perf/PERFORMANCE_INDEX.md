# The performance index

The same index and harness as `aburan28/crypto` `docs/perf/PERFORMANCE_INDEX.md`;
here the kernels live in `suite/examples/perfbench` and call `cryptanalysis_suite`.
The C library (`src/`, `include/`) is measured by `tools/ca_perfbench.c`, which
speaks the same command-line protocol, so `perfindex.py` compares it the same way.

One number for "how much faster is this revision's code than that one's",
computed the same way every time, refused when the two revisions compute
different answers, and reported with its noise.

```bash
# 1. Build both sides with the SAME harness (this tree's suite/examples/perfbench).
python3 scripts/perf/perfindex.py build --ref <base-rev> --out /tmp/pi-base
python3 scripts/perf/perfindex.py build --current      --out /tmp/pi-cand
# 2. Wall time, paired and interleaved, one thread (the headline).
python3 scripts/perf/perfindex.py compare --base /tmp/pi-base/perfbench \
    --cand /tmp/pi-cand/perfbench --rounds 5 --threads 1 --out /tmp/pi-1t
# 3. The same at every core, and the deterministic instruction count.
python3 scripts/perf/perfindex.py compare ... --threads 4 --out /tmp/pi-4t
python3 scripts/perf/perfindex.py instr --base ... --cand ... --out /tmp/pi-ir
```

The C library's harness is built the same way with `--c` (CMake instead of
Cargo; the ref side gets this tree's `tools/ca_perfbench.c` overlaid and, if
it predates the target, a guarded `ca_perfbench` target appended to its
`CMakeLists.txt`); `compare` and `instr` need no flag, they drive any binary
that speaks the protocol:

```bash
python3 scripts/perf/perfindex.py build --c --ref <base-rev> --out /tmp/ci-base
python3 scripts/perf/perfindex.py build --c --current      --out /tmp/ci-cand
python3 scripts/perf/perfindex.py compare --base /tmp/ci-base/ca_perfbench \
    --cand /tmp/ci-cand/ca_perfbench --rounds 5 --threads 1 --out /tmp/ci-1t
python3 scripts/perf/perfindex.py instr --base /tmp/ci-base/ca_perfbench \
    --cand /tmp/ci-cand/ca_perfbench --out /tmp/ci-ir
```

Its kernels (`ca_perfbench list --full`) cover `field_ec` (Montgomery
arithmetic, `ca_powmod`/`ca_invmod`/`ca_sqrtmod_prime`, primality and
factoring, affine and batched EC addition, scalar multiplication, point
counting), `dlp` (rho, kangaroo, BSGS, grumpy giants, Pohlig-Hellman,
Bernstein-Lange precomputation, GLV rho, the emulated GPU rho, Cheon) and
`relation` (index-calculus precomputation and individual logs, the sparse
Lanczos and dense elimination modulo a prime).  All run one thread except
`dlp/c_rho_ec44_mt`, which takes `RAYON_NUM_THREADS` and fingerprints only
the recovered logarithms.  Fingerprints cover the answers and the solvers'
deterministic work counters (`group_ops`, `iterations`, `table_entries`,
`collisions`), not `seconds` or the `bytes_peak` memory estimate.

## What it measures, and what it does not

`suite/examples/perfbench` is a registry of **kernels**: each runs a fixed,
seeded input through an existing public entry point of the library and
returns a 64-bit **fingerprint** of everything it computed (reduced
matrices, bases, models, recovered logarithms, point coordinates).  The
kernels are grouped into eight **areas**:

| area | covers |
|:--|:--|
| `gf2_la` | dense/sparse linear algebra over F₂ (Four Russians, echelon forms) |
| `bool_gb` | Gröbner bases over F₂: F4/F5, Macaulay/XL, crossbred, FES |
| `fp_gb` | Gröbner bases over F_p and extension fields: F4, F5/signature, tower F4 |
| `sat` | CDCL with native XOR clauses; Semaev and WDSat encodings |
| `pdp` | point decomposition: summation polynomials and decomposition oracles |
| `field_ec` | F₂ᵐ, F_p, F₃ᵐ arithmetic; point addition; scalar multiplication; batch inversion |
| `relation` | relation collection, index-calculus pipelines, relation-matrix algebra |
| `dlp` | generic discrete logarithm: Pollard rho, BSGS, kangaroo, Pohlig–Hellman |

These are **engineering** measurements in the sense of `AGENTS.md` (and the crypto repository's §3).
A faster kernel lowers the *time per counted operation*; it does not
change the operation count `S`, a degree of regularity, a relation
yield, or any exponent, and it is never by itself an end-to-end method
speedup (§8).  A change that alters what a kernel computes changes its
fingerprint and is refused here: that is an algorithmic change and is
measured under §8's rules, not this index's.

## The formula

For kernel `k`, paired round `r`, baseline `A`, candidate `B`, and `T` the
median wall time of one harness invocation (warm-up discarded, `S` timed
samples):

```
d(k,r)  = ln( T_A(k,r) / T_B(k,r) )                 paired log-ratio
s(k)    = exp( median_r d(k,r) )                    kernel speedup
A(a)    = exp( (1/|a|) · Σ_{k∈a} ln s(k) )          area index (geometric mean)
PI      = exp( Σ_a w(a) · ln A(a) ),  Σ_a w(a) = 1  performance index
```

* **Validity gate.** If any two runs of a kernel — baseline, candidate, or
  a repeat — return different fingerprints, the comparison is INVALID and
  no index is reported.  Every kernel also checks, inside one process, that
  every sample returns the same fingerprint.
* **Weights.** `docs/perf/weights.json`; equal by default, so each area
  counts once however many kernels it has.  A reweighting is a new index
  and is reported as such, never mixed with the old one.
* **Why a geometric mean.**  It is unit-free (a kernel measured in
  microseconds and one in seconds count alike), symmetric (a 2× gain and a
  2× loss cancel exactly), and it is the only mean for which "the index of
  B over A times the index of C over B is the index of C over A".
* **Pairing.** Each round runs `A`, `B` and a second baseline `A'` for
  every kernel, back to back, with the arm order rotated each round and
  the kernel order shuffled (seeded).  Drift in the host's load lands on
  both sides of a pair instead of on one side of the comparison.
* **Noise (A/A).** `n(k,r) = ln(T_A / T_A')` is the baseline against
  itself.  `σ(k) = 1.4826 · median_r |n(k,r)|` (a robust standard
  deviation).  A kernel's verdict is **faster** only when the 95% bootstrap
  interval of `median_r d(k,r)` excludes zero **and**
  `ln s(k) > max(2σ(k), ln 1.02)`; symmetrically **slower**; otherwise
  **neutral**.  A difference inside the A/A spread is not a result.
* **Uncertainty of PI.** Rounds are resampled jointly (a bootstrap over
  rounds, 2000 resamples), since all kernels in a round share the host's
  state at that time.
* **Threads.** The headline index is at `RAYON_NUM_THREADS=1`.  The
  many-thread index is reported beside it; a multi-core gain must not
  regress the single-thread index (§10).
* **Instruction counts.** `perfindex.py instr` runs each kernel once under
  callgrind, restricted to the timed region (`perfbench_measured_region`),
  and applies the same formula to instruction counts `Ir`.  It is
  deterministic and immune to host load, and it is blind to memory stalls,
  to instruction latency and to instruction width: valgrind has no
  AVX-512, so it measures the scalar/AVX2 dispatch paths, and a 64-bit
  divide counts as one instruction, so replacing a `%` by a few
  multiplications *raises* `Ir` while the time falls (the index-calculus
  trial division in `cryptanalysis`: `Ir` 0.82×, wall 2.57× faster).
  Instrumentation is switched on and off by client requests in the
  measured region, so work on every thread counts, including private
  thread pools.  Report it next to wall time, never instead of it.

## From the index to a workload

The index weights areas equally; a particular pipeline does not.  If a
workload spends fraction `f(a)` of its baseline time in area `a`
(Σ f = 1, from a profile of that workload), its projected speedup is
Amdahl's

```
speedup_workload = 1 / Σ_a ( f(a) / A(a) )
```

— a projection, labelled as one, until the workload itself is rerun on
both revisions.  Where a workload has its own frozen benchmark (the
`ic-e2e-benchmark` rungs, `examples/pdp_bench`, the frozen WDSat suite),
that benchmark's paired rerun is the measurement and this projection is
only a cross-check.

## Rules for kernels

1. **Public entry points only.**  A kernel calls code the research
   pipelines call, so the baseline revision builds the same harness and
   the speedup is the speedup of that code.  A kernel that needs a new
   API has no baseline and is added after the change, with its own
   baseline from then on.
2. **Fixed inputs, fingerprinted outputs.**  Seeded generators only;
   fingerprint everything that is returned (not a length or a count
   alone), in a canonical order.
3. **Stable IDs.**  `area/name`.  An ID is never reused for different
   work; changing a kernel's input or size means a new ID.
4. **Size.**  1–300 ms per run at one thread on a 2 GHz x86-64, so a
   comparison of every quick kernel stays under a few minutes a round.
   Slower cells are `Tier::Full`.
5. **One-time costs outside the timer.**  Input construction happens in
   `setup`; per-sample restoration of consumed inputs in `prepare`.
   Lazy statics and thread pools are warmed by the discarded warm-up runs.

## Reporting a change

A performance change carries, in its commit or PR: the host manifest
(`compare.json` records it), the A/A spread, the per-kernel table with
fingerprints, the single- and many-thread indices, the instruction-count
index, and the changes that were tried and rejected with their numbers
(§10).  It is classified **engineering** (§3).

## Build settings tried

| setting | result | decision |
|:--|:--|:--|
| `lto = "fat"`, `codegen-units = 1` (2026-09-26, crypto, bool_gb + gf2_la kernels, 3 paired rounds) | no kernel reliably faster; `gf2_la/rref_random_2048` 0.77× (slower); area indices 1.005× / 0.769×; build 3 min | rejected: the default profile stays |

## Changes tried and rejected

| change | measurement | decision |
|:--|:--|:--|
| `f4_gf2::xor_then_lead` as two non-aliasing slices (vectorisable XOR, `position` for the lead) instead of raw-pointer loops (2026-09-26) | suite f4gf2/f4batch kernels 0.81–0.99× vs the previous commit, 5 paired rounds, all inside the A/A spread and none faster: the rows are a few words long | not landed |
| `bsgs_fast::FastField::inv` by extended Euclid instead of Fermat (considered) | not built: a 63-bit Euclid is ~40 dependent 64-bit divisions against ~94 pipelined Montgomery multiplications | not landed |
| `prime_orbit_index_calculus::add_r`/`sub_r` with a conditional subtraction for reduced operands (2026-09-26) | orbit rho 1.01×, orbit IC 0.93×, both inside the A/A spread | not landed |

## C rho index fast path: exploratory measurement (2026-10-14)

The C rho walk normally chooses a power-of-two multiplier count.  The
`src/rho.c` change on `codex/cryptanalysis-rho-index-fastpath` uses a mask for
that case and retains fast remainder for explicit non-power-of-two counts.
This is an engineering change to index calculation; it does not change the
walk or its operation count.  The baseline is `c25dd9f940e92c9740eab79905b3a475d9f25cff`
(the parent branch of this stacked change).  Both arms used AppleClang 17,
Release CMake builds, the same `tools/ca_perfbench.c`, one thread, five paired
rounds, one sample per arm, and `--max-seconds 1`.  The exact comparison was:

```sh
python3 scripts/perf/perfindex.py compare \
  --base build-speed-baseline/ca_perfbench \
  --cand build-speed-candidate/ca_perfbench \
  --filter dlp/c_rho_ec36 --filter dlp/c_rho_zp40 \
  --rounds 5 --samples 1 --max-seconds 1 --threads 1 \
  --out build-speed-candidate/rho-compare
```

Raw invocation times in milliseconds are retained below by round;
`A` is baseline, `B` is candidate, and `A2` is the repeat baseline.  All
rounds had identical fingerprints across arms and repeats:
`f4277749c86fe1c9` for EC36 and `8e58f9123c615d90` for Zp40.

| round | EC36 A | EC36 B | EC36 A2 | Zp40 A | Zp40 B | Zp40 A2 |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 170.471 | 32.576 | 54.369 | 22.501 | 16.865 | 34.783 |
| 2 | 249.327 | 43.036 | 47.220 | 11.312 | 20.652 | 13.211 |
| 3 | 51.207 | 29.681 | 32.428 | 18.694 | 23.647 | 14.748 |
| 4 | 37.174 | 142.014 | 48.408 | 20.045 | 32.659 | 40.849 |
| 5 | 62.172 | 23.209 | 44.354 | 28.041 | 17.285 | 28.704 |

The harness classified both kernels **neutral**: EC36's paired median ratio
was 2.679× (95% bootstrap interval 0.262–5.793×, A/A noise 96.9%), and
Zp40's was 0.791× (0.548–1.622×, A/A noise 42.1%).  Host load average was
80.5–87.7 on 14 logical cores during the run.  This result confirms output
identity on those fixtures, but cannot establish a wall-time gain or rule out
a regression.  No instruction-count measurement was available on this macOS
host.  A quiet, isolated rerun of the same frozen comparison is needed for a
performance claim.  The focused `group`, `bsgs`, and `rho` C tests passed in
both builds; the candidate rho test additionally exercises `r=15`.
