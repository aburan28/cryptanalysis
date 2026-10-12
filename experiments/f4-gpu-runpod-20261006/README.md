# F4 on a real GPU: an RTX 5090 on Runpod (2026-10-06)

The device measurements the September experiment
([`../f4-gpu-20260925`](../f4-gpu-20260925/RESULT.md)) could not make:
the large-matrix elimination (`F4_F2_ECHELON=cuda`,
`suite/cuda/f4_gf2_echelon.cuh`) against the host on single matrices, on
`f4_degree_bench` and on `dreg_sweep`, and the batched per-node decider
against the host's engines. Findings, tables and caveats are in
[RESULT.md](RESULT.md).

Reproduce on a Runpod pod with `cloud/runpod_pod.py` (needs
`RUNPOD_API_KEY`), which rents it, ships the checkout, runs the script,
copies the receipts back and deletes it:

```sh
cloud/runpod_pod.py run f4 --gpu "NVIDIA GeForce RTX 5090" \
    --out experiments/f4-gpu-runpod-20261006/rerun -- \
    'bash experiments/f4-gpu-runpod-20261006/pod_matrix.sh experiments/f4-gpu-runpod-20261006/rerun'
```

On any CUDA host, `pod_matrix.sh OUT` alone runs the same measurements.
