# shellcheck shell=bash
# pod_env.sh - the suite's GPU toolchain on a Runpod pod, for `source`.
#
# Installs Rust (stable, minimal profile) and NVRTC 12 (the pip wheel) when they
# are missing, and exports what the suite's CUDA paths read.  Used by
# cloud/runpod_pod.py before its command and by every cairn queue job
# (cloud/cairn_queue.py) before job_runner.sh.  The driver comes with the pod.
export LC_ALL=C.UTF-8 PATH="$HOME/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null; then
  curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs |
    sh -s -- -y -q --profile minimal --default-toolchain stable >/dev/null
fi
if ! python3 -c 'import nvidia.cuda_nvrtc' 2>/dev/null; then
  pip3 install -q --break-system-packages nvidia-cuda-nvrtc-cu12 >/dev/null
fi
CA_NVRTC_LIB=$(python3 -c 'import glob, nvidia.cuda_nvrtc as m
print(glob.glob(m.__path__[0] + "/lib/libnvrtc.so.12")[0])')
export CA_NVRTC_LIB
