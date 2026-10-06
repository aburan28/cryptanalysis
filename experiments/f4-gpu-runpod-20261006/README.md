# F4 on a real GPU: an RTX 5090 on Runpod (2026-10-06)

The device measurements the September experiment
([`../f4-gpu-20260925`](../f4-gpu-20260925/RESULT.md)) could not make:
the large-matrix elimination (`F4_F2_ECHELON=cuda`,
`suite/cuda/f4_gf2_echelon.cuh`) against the host on single matrices, on
`f4_degree_bench` and on `dreg_sweep`, and the batched per-node decider
against the host's engines. Findings, tables and caveats are in
[RESULT.md](RESULT.md).

Reproduce on a pod rented with `../f4-gpu-20260925/runpod_bench.py`
(needs `RUNPOD_API_KEY`):

```sh
B=experiments/f4-gpu-20260925/runpod_bench.py
python3 $B up f4 --gpu "NVIDIA GeForce RTX 5090" --min-vcpu 16 \
    --image runpod/base:1.0.2-ubuntu2404
python3 $B sync f4
python3 $B ssh f4 -- 'bash /root/cryptanalysis/experiments/f4-gpu-runpod-20261006/pod_matrix.sh /root/receipts'
python3 $B fetch f4 /root/receipts /tmp/f4-runpod
python3 $B down f4
```

On any CUDA host, `pod_matrix.sh OUT` alone runs the same measurements.
