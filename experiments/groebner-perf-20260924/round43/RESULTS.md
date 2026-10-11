# Local correctness, without a performance claim

The final package passed 17,258 systems in both optimized and UBSan builds:
34,516 native system runs, with 29 failure/lifecycle guard groups per build.
An independent report audit recomputed all witnesses, affine ranks and
complete roots from the frozen original equations. The package also matches
the isolated prototype's proof payloads, roots, integer work and guards.

The machine is a physical Apple M4 Pro with 48 GiB RAM, running macOS ARM64.
The exact OS, compiler commands, source hashes, binary hashes and corpus
digest are retained in [the local evidence](results/local-m4/). Native
binaries are build artifacts and are not checked into Git. CI separately
rebuilds on Linux and macOS and retains its actual libraries in downloadable
artifacts. A hosted runner correctness pass is not a physical-device timing
result.

This validates complete roots of each bounded residual system. It does not
establish complete global Gröbner query correctness, a 30-variable query,
GPU support or a speedup. No timing workload is part of this package;
`candidate_id` and `online_speedup` remain null.

The subsequent experiment is to integrate checked affine witnesses at the
existing rank-deficient residual fallback, retain all full-basis checks,
bound the entire query's work/memory, and measure fresh complete queries
against the accepted CPU and Metal paths. The proposed ten-variable residual
route requires bounded coefficient-table tiling before widening the full
query; its untiled table would exceed the current memory guard.
