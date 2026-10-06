# Retain owned Metal buffer mappings

This opt-in experiment removes repeated Objective-C `contents` calls from indexed access to the coefficient and root buffers. The generated host stores each shared buffer’s CPU pointer once after successful allocation. It retains the owning `MTLBuffer` under ARC until the workspace is destroyed, never replaces that allocation, and preserves the existing command completion wait before CPU reads. Only addresses are reused; every target receives fresh coefficients, solving and exact independent certification.

Apple documents shared resources as memory accessible to both CPU and GPU and requires the application to synchronize access. This implementation retains the existing synchronization. [Apple resource storage guidance](https://developer.apple.com/documentation/metal/choosing-a-resource-storage-mode-for-apple-gpus), [shared storage synchronization](https://developer.apple.com/documentation/metal/mtlresourceoptions/storagemodeshared). The lifetime argument above comes from this implementation’s ownership and absence of reallocation.

The generator pins round22 host, generator and native test sources. Its test reverses the mapping-only changes and requires byte-for-byte equality with the frozen host. All generated decoder, kernels, validation, exact basis proof and direct original-equation evaluator remain unchanged. Neither the producer nor its roots become the independent verifier’s oracle.

## Complete-query results

Five arms compare frozen packed CPU, the new sparse-proof CPU, frozen coefficient-word Metal, retained mappings with blocking completion, and retained mappings with bounded polling. CPU stays the default. Explicit unavailable GPU requests remain errors. This is an evaluation/Buchberger–Möller PDP experiment, not F4/F5, full IC, natural relation yield or a new asymptotic algorithm. The existing 20-variable enumeration limit remains.

Two complete frozen-suite runs on a physical Apple M4 Pro pass the predeclared load gate and verify all 5,120 queries (160 warmups plus 4,960 measured queries). Each of 16 planted public-point controls gets 31 paired repetitions with randomized arm order. The interval includes fresh packed descent, producer, independent certificate, direct original equations and complete curve replay; setup and fixture construction are separate. A second Python curve audit is recorded outside this timing boundary. Reports retain all attempted arms, load samples, status, exclusive phase costs, source/build/binary identities and recoverable journals. Load admission is necessary but does not establish an exclusive host.

The blocking mapped backend beats both CPU paths in both runs on two of the three degree-63, 20-variable controls. These are specific exploratory control results, not a general crossover rule. The first-run 18-variable wins do not reproduce. Smaller controls regress; degree-31 20-variable results are mostly inconclusive. All controls appear below. Ratios are sparse CPU wall time divided by mapped blocking wall time; intervals are per-control 95% paired bootstrap intervals, without a multiple-comparison claim.

| Control | Initial gain [95% interval] | Confirmation gain [95% interval] | Beats both CPUs in both runs |
| --- | --- | --- | --- |
| n31-m3-ell6-seed101 | 1.222× [1.196, 1.248] | 0.899× [0.824, 0.965] | no |
| n31-m3-ell6-seed102 | 1.062× [0.884, 1.226] | 0.979× [0.921, 1.038] | no |
| n31-m3-ell6-seed103 | 1.212× [1.184, 1.238] | 0.941× [0.898, 0.983] | no |
| n31-m3-ell6-seed104 | 1.190× [1.165, 1.217] | 0.835× [0.726, 0.942] | no |
| n31-m3-ell6-seed105 | 1.224× [1.157, 1.291] | 0.860× [0.787, 0.921] | no |
| n31-m3-ell6-seed106 | 1.188× [1.135, 1.230] | 0.736× [0.652, 0.830] | no |
| n31-m3-ell3-seed101 | 0.552× [0.514, 0.587] | 0.410× [0.338, 0.485] | no |
| n31-m3-ell4-seed101 | 0.629× [0.575, 0.682] | 0.414× [0.371, 0.461] | no |
| n11-m3-ell2-seed101 | 0.498× [0.450, 0.553] | 0.387× [0.327, 0.446] | no |
| n83-m3-ell2-seed101 | 0.933× [0.845, 0.991] | 0.966× [0.953, 0.976] | no |
| n31-m2-ell10-seed201 | 1.006× [0.987, 1.024] | 1.015× [1.003, 1.028] | no |
| n31-m2-ell10-seed202 | 1.011× [0.994, 1.026] | 1.006× [0.992, 1.018] | no |
| n31-m2-ell10-seed203 | 1.010× [0.952, 1.084] | 1.010× [0.993, 1.025] | no |
| n63-m2-ell10-seed201 | 1.122× [1.063, 1.196] | 1.123× [1.112, 1.135] | yes |
| n63-m2-ell10-seed202 | 1.022× [0.891, 1.121] | 1.106× [1.090, 1.122] | no |
| n63-m2-ell10-seed203 | 1.142× [1.090, 1.188] | 1.116× [1.102, 1.129] | yes |

On degree-63 seed 201, sparse CPU / mapped medians are 5.283 / 4.668 ms initially and 4.826 / 4.286 ms in confirmation. On seed 203 they are 5.326 / 4.657 ms and 4.800 / 4.309 ms. The paired estimates are computed from each matched repetition, not ratios of marginal medians.

The 18-variable seed-101 basis-check phase is stable near 0.286 ms for the original GPU host versus 0.052 ms with retained mappings in both runs. Its GPU execution/completion phase changes from roughly 0.208 to 0.722 ms between runs, which explains why the complete-query advantage does not persist despite the host improvement. On degree-63 seed 201, the same proof phase falls from about 1.226 to 0.219 ms initially and 1.139 to 0.204 ms in confirmation. These marginal internal diagnostics are not additive totals.

## Correctness and provenance

22 test groups cover portable defaults/capability checks, generation guards, malformed ABI and certificates, direct equations, wide limbs, duplicates, zero/unit/many roots, fresh targets, reuse, concurrent calls, close lifetime, five-arm parity, source/binary receipt corruption, admission and interrupted journal recovery. The GPU integration includes 96 certificate comparisons, 8,352 direct equation evaluations and 20 complete query comparisons, plus 10 five-arm queries. Two native device configurations (optimized 256 threads and UBSan 64 threads) each check 40 cases, 26,315,144 intermediate words, 26,315,144 final truth words and 148,248 root words against direct sparse evaluation.

The final-source correctness trace independently verifies another 240 queries and is explicitly ineligible for performance claims. The two timing reports predate stricter receipt-key validation in `audit.py`; every archived numerical source, native generator, benchmark, wrapper and journal remains byte-for-byte identical to the PR. `verify_evidence.py` permits exactly that one historical audit-source difference, applies the current stricter audit to both reports, and requires every final trace source to match. The new tests were added after the timing reports; no archived data or source snapshot was rewritten.

No CUDA, OpenCL, physical x86 GPU or automatic dispatch claim is made. Metal requires macOS and an available device; portable CPU verification remains usable without it. Memory reports include the shared allocation footprint and process high-water mark, not isolated per-query peak memory.

## Reproduce

Use ordinary Python for this native/Metal experiment; it does not import Sage. From the repository root:

```sh
python3 -m pip install numpy==2.4.0
python3 experiments/groebner-perf-20260924/round20/build.py
python3 experiments/groebner-perf-20260924/round23/build.py
python3 experiments/groebner-perf-20260924/round22/build.py
python3 experiments/groebner-perf-20260924/round24/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round24 -p 'test_*.py' -v
experiments/groebner-perf-20260924/round24/build/test-mapped 256
experiments/groebner-perf-20260924/round24/build/test-mapped-ubsan 64
python3 experiments/groebner-perf-20260924/round24/verify_evidence.py
python3 experiments/groebner-perf-20260924/round24/benchmark.py --repetitions 31 --admission-wait-seconds 240 --output /tmp/mapped-metal-new.json.gz
python3 experiments/groebner-perf-20260924/round24/audit.py /tmp/mapped-metal-new.json.gz
```

The Linux CI job builds and tests the portable paths and audits retained evidence. macOS also rebuilds every native dependency, runs the actual device checks and all five query arms, and retains a bounded-admission comparison or explicit rejection. Hosted GPU results describe the reported device; they are not automatically physical Apple hardware evidence.

The next experiment is to overlap independent GPU evaluation with CPU basis construction while preserving separate arithmetic and charging synchronization, fallback and full certification. Any adoption in IC needs a new immutable candidate identity, one previously unseen public target, all target-dependent attempts and independent scalar replay, paired against one-target rho on the same point.
