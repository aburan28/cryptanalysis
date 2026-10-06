# F4 kernel, F5 and GPU experiment (2026-09-25)

Measurements behind the `f4_gf2` / `f4_batch` / `f4_gpu` changes to the
suite's Gröbner decomposition oracle. The findings, tables and caveats are
in [RESULT.md](RESULT.md).

Reproduce on the same host:

```sh
cd suite && cargo build --release --features gpu-emulator --bin ca-ic --examples
../experiments/f4-gpu-20260925/run_paired.sh          # receipts/e2e, receipts/stage
./target/release/examples/f4_degree_bench --max-degree 5 --out /tmp/degree
./target/release/examples/f4_batch_bench --degree 23 --curve-a 1 --targets 64 \
    --modes sequential,rayon,lockstep:cpu,lockstep:emulate --replay-cap 20000 --out /tmp/batch
F4_F2_RREF=reference ./target/release/examples/dreg_sweep --d-max 5 --trials 4 --n-max 13
./target/release/examples/dreg_sweep --d-max 5 --trials 4 --n-max 13
cuda/build_kernel.sh "$(../ecc2k130/scripts/fetch_cuda.sh)/bin/nvcc"
python3 ../experiments/f4-gpu-20260925/records.py      # manifests, runs.jsonl, summary.json
```

`records.py` hashes the measured sources as of `SOURCE_COMMIT`, so the
candidate IDs do not drift with later edits; every record it writes passes
`../ic-candidate-catalog/analyze.py`.
