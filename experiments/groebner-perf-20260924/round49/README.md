# GPU affine projection with original-equation witnesses

Round49 is an opt-in producer experiment for bounded Boolean quadratic queries. It targets the CPU affine-projection work remaining after round48's independent multiplier-check improvements. `adapter.ProjectionQuery(..., backend="metal", identity="factored_local")` uses the new producer and the unchanged round48 independent checker. Existing accepted query factories and dispatch defaults are unchanged. `backend="cpu"` retains the portable CPU algorithm; more than 32 equations explicitly use the existing CPU shape fallback even from a Metal build.

The GPU already carries original-equation combination vectors while constructing a lifted RREF. After writing that original result, the same SIMD group eliminates quadratic columns and reduces the remaining affine rows. It returns those rows with their witnesses in the same command buffer. The host builds the existing constant, affine-multiplier or tagged partial-affine certificate, including exact residual enumeration where needed. Each solve uploads fresh coefficients. No target answer, coefficient table or proof is cached.

The independent checker reconstructs coefficients from the original ANF, checks every required identity and the complete root count, and verifies the reduced basis. Complete queries also evaluate the chosen root against the original equations and replay the signed curve relation. Device ranks and rows are proof proposals, not verification evidence. A different valid GPU witness can change proof bytes without changing the root set or basis.

## Reproduce

Use standalone Python 3.12+ and a C++17 compiler. These are not Sage jobs. From the repository root:

```sh
for version in 20 23 31 32 33 34 35 36 37 38 44 48 49; do
  python3 "experiments/groebner-perf-20260924/round${version}/build.py"
done
python3 -m unittest discover -s experiments/groebner-perf-20260924/round49 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round49/validate_native.py --output /tmp/gpu-affine-correctness.json.gz
python3 experiments/groebner-perf-20260924/round49/audit_queries.py --input /tmp/gpu-affine-correctness.json.gz --output /tmp/gpu-affine-audit.json
```

On macOS, build round44 and round49 with `--metal`. Run the tests with `QUADRATIC_TEST_METAL=1` only after the actual device probe succeeds, pass `--metal` to validation, and run `test_projection.py --output /tmp/gpu-affine-oracle.json`. An unavailable device remains an explicit result, not a device correctness pass. CI rebuilds CPU optimized and UBSan libraries on Linux and macOS and records the actual available Metal device; hosted or virtualized devices do not establish physical hardware coverage or speedups.

The raw-device oracle compares every returned affine row with the XOR of the original equations selected by its witness and compares the entire affine consequence space with separate Python row reduction. It covers exhaustive small matrices, equation boundaries through 32, all residual dimensions 1..10, fresh inputs with and without symmetry, constants, zero and rank-deficient systems, mutations, and captured specializations independently reconstructed from frozen ANFs. The full validation retains 6,001 polynomial controls and 18 complete public-point queries, with projection and partial production on/off under CPU optimized, CPU UBSan and available Metal. Root-limit outcomes remain inconclusive records. CPU and disabled-projection proofs must match the accepted round44 evidence exactly; enabled GPU proofs are independently checked.

The measurement plan compares accepted CPU/Metal paths, accepted tiled checking, GPU projection disabled, and projection with full/tiled checking. Every arm includes fresh solving and independent certification of one complete query; reusable setup is recorded separately. All failed admissions and runs remain records. Run `measure_paired.py --correctness ... --audit ... --output ...` only after correctness and independent audit pass, with no other owned build, test or benchmark running. `analyze_paired.py --input ... --output ...` applies the frozen matched-ratio plan. See [PROTOCOL.md](PROTOCOL.md) for representation, bounds and accounting.

This is polynomial linear algebra with certificate construction, not a new asymptotically faster Gröbner algorithm. It does not establish a global F4/F5 record, natural relation yield, high-degree-regularity scaling, CUDA/OpenCL performance or a recovered single-target IC/rho speedup. `candidate_id` and `online_speedup` remain null.
