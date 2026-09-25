"""Run the F4 GPU benchmark matrix on a Modal GPU with many CPU cores.

    modal run experiments/f4-gpu-20260925/modal_f4.py
    modal run experiments/f4-gpu-20260925/modal_f4.py --gpu RTX-PRO-6000 --cpu 48
    modal run experiments/f4-gpu-20260925/modal_f4.py --targets 256 --batches 64

One container gets the GPU and `--cpu` physical cores as both request and
hard limit, so the "all cores" numbers are the request's, not whatever the
host has free; Modal rejects a request above its per-container maximum
with an InvalidError, so lower `--cpu` if that happens.  Rayon sizes its
pool from the CPUs the container exposes, which the receipts record next
to the cgroup quota; `--threads N` pins it instead.

The image builds `suite/` in release mode on NVIDIA's CUDA devel image,
whose NVRTC compiles the kernel for the GPU found at run time; then
`gpu_bench.py` runs the stage ladder, the batched-decision modes and replay,
and complete DLPs on the cores and on the GPU, checking every answer.
Its receipts come back to `receipts/gpu/<gpu>-cpu<n>-<UTC time>/`, and the
command fails if any check did.

The defaults (`--gpu H100 --cpu 32 --memory 32768`) can also come from
F4_GPU, F4_CPU and F4_MEMORY_MB; F4_CUDA_VERSION and F4_RUST pin the CUDA
image and the Rust toolchain.  Valid GPU names include T4, L4, A10, L40S,
A100, A100-80GB, RTX-PRO-6000, H100, H200 and B200.
"""

import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import time

import modal

GPU = os.environ.get("F4_GPU", "H100")
CPU = float(os.environ.get("F4_CPU", "32"))
MEMORY_MB = int(os.environ.get("F4_MEMORY_MB", "32768"))
CUDA_VERSION = os.environ.get("F4_CUDA_VERSION", "12.8.1")
RUST = os.environ.get("F4_RUST", "1.98.1")
if not re.fullmatch(r"\d+\.\d+\.\d+", CUDA_VERSION):
    raise ValueError("F4_CUDA_VERSION must be a toolkit version such as 12.8.1")

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
REMOTE = "/root/cryptanalysis"
EXPERIMENT = "experiments/f4-gpu-20260925"
BENCH = f"{REMOTE}/{EXPERIMENT}/gpu_bench.py"
OUT = "/tmp/f4-gpu"
CUDA_LIB = "/usr/local/cuda/lib64"
HOUR = 60 * 60

image = (
    modal.Image.from_registry(f"nvidia/cuda:{CUDA_VERSION}-devel-ubuntu24.04", add_python="3.12")
    .entrypoint([])
    .apt_install("build-essential", "ca-certificates", "curl")
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | "
        f"sh -s -- -y --profile minimal --default-toolchain {RUST}"
    )
    .env({
        "PATH": "/root/.cargo/bin:/usr/local/nvidia/bin:/usr/local/cuda/bin:"
                "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "CARGO_TARGET_DIR": "/root/target",
        "CA_NVRTC_LIB": f"{CUDA_LIB}/libnvrtc.so.12",
    })
    # The suite embeds this corpus at compile time, from outside suite/.
    .add_local_file(REPO / "challenges/elliptic/corpus.json",
                    f"{REMOTE}/challenges/elliptic/corpus.json", copy=True)
    .add_local_dir(REPO / "suite", f"{REMOTE}/suite", copy=True,
                   ignore=["target", "target/**", "**/__pycache__", "**/*.pyc"])
    .run_commands(
        f"cd {REMOTE}/suite && cargo build --release --locked --features gpu-emulator "
        "--bin ca-ic --example f4_batch_bench --example groebner_stage_bench"
    )
    # Mounted rather than copied: editing the driver rebuilds nothing.
    .add_local_file(HERE / "gpu_bench.py", BENCH)
    .add_local_file(HERE / "receipts/stage/fast-rep1/stage.json",
                    f"{REMOTE}/{EXPERIMENT}/receipts/stage/fast-rep1/stage.json")
)

app = modal.App("f4-gpu", image=image)


@app.function(gpu=GPU, cpu=(CPU, CPU), memory=MEMORY_MB, timeout=3 * HOUR)
def bench(bench_args: list[str], request: dict) -> dict:
    """Run `gpu_bench.py` here and return its exit status and receipts."""
    os.environ["LD_LIBRARY_PATH"] = ":".join(
        p for p in (CUDA_LIB, os.environ.get("LD_LIBRARY_PATH")) if p)
    if request.get("threads"):
        os.environ["RAYON_NUM_THREADS"] = str(request["threads"])
    out = pathlib.Path(OUT)
    code = subprocess.run([sys.executable, BENCH, "--out", OUT, *bench_args]).returncode
    if not out.exists():
        return {"exit": code, "tarball": None}
    (out / "modal_request.json").write_text(json.dumps(
        {**request, "cuda_image": f"nvidia/cuda:{CUDA_VERSION}-devel-ubuntu24.04",
         "rust": RUST, "bench_args": bench_args}, indent=2, sort_keys=True) + "\n")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(out, arcname=".")
    return {"exit": code, "tarball": buf.getvalue()}


@app.local_entrypoint()
def main(gpu: str = GPU, cpu: float = CPU, memory: int = MEMORY_MB, threads: int = 0,
         targets: int = 1024, batches: str = "64,1024", replay_cap: int = 200_000,
         replay_batch: int = 16_384, skip_cuda: bool = False):
    bench_args = ["--targets", str(targets), "--batches", batches,
                  "--replay-cap", str(replay_cap), "--replay-batch", str(replay_batch)]
    if skip_cuda:
        bench_args.append("--skip-cuda")
    request = {"gpu": gpu, "cpu": cpu, "memory_mb": memory, "threads": threads or None}
    print(f"Modal request: {json.dumps(request)}; gpu_bench.py {' '.join(bench_args)}")
    fn = bench.with_options(gpu=gpu, cpu=(cpu, cpu), memory=memory)
    result = fn.remote(bench_args, request)
    if result["tarball"] is None:
        raise SystemExit(f"gpu_bench.py exited {result['exit']} before writing receipts")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    slug = re.sub(r"[^A-Za-z0-9]+", "-", gpu).strip("-").lower()
    dest = HERE / "receipts" / "gpu" / f"{slug}-cpu{cpu:g}-{stamp}"
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(result["tarball"]), mode="r:gz") as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)
    print(f"receipts in {dest}")
    if result["exit"] != 0:
        raise SystemExit(f"gpu_bench.py exited {result['exit']}: see {dest}/summary.json")
