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
  deterministic and immune to host load, and it is blind to memory stalls
  and to instruction width: valgrind has no AVX-512, so it measures the
  scalar/AVX2 dispatch paths.  Report it next to wall time, never instead
  of it.

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
