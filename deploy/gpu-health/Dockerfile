# The GPU health check: ec2k-gpu (the ECC2K-130 Pollard rho walk, ecc2k130/)
# and the orchestrator that runs it on every visible GPU and gives a verdict.
#
#   docker build -f deploy/gpu-health/Dockerfile -t gpu-health:dev .
#   docker run --rm --gpus all gpu-health:dev                  # 60 s on every GPU
#   docker run --rm --gpus all -e GPU_HEALTH_SECONDS=120 gpu-health:dev
#
# The build context is the repository root: the client is ecc2k130/ and the
# golden model its reports are checked against is fpga/model/.  The binary is
# built for sm_80 through sm_120 plus compute_120 PTX with the CUDA runtime
# linked in, so the image needs no CUDA install, only an NVIDIA driver recent
# enough for CUDA 13.3 and the NVIDIA container runtime (which injects the
# driver's libcuda and nvidia-smi).  Pre-Ampere GPUs cannot run it: the walk's
# products are carry-less multiplies (clmad), which exist from sm_80.
#
# The build checks what it ships: the host test (every packed routine against
# the golden model, the campaign's known answers, the health checks' own
# tests) and the finished binary's `check --kat` must pass, and the binary
# must not load a shared CUDA runtime.

ARG DEBIAN=bookworm

# ---- build ------------------------------------------------------------------
FROM debian:${DEBIAN}-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates python3 python3-pip unzip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY fpga/model/ fpga/model/
COPY ecc2k130/Makefile ecc2k130/
COPY ecc2k130/include/ ecc2k130/include/
COPY ecc2k130/src/ ecc2k130/src/
COPY ecc2k130/scripts/fetch_cuda.sh ecc2k130/scripts/
COPY ecc2k130/tests/campaign-kat.hex ecc2k130/tests/
WORKDIR /src/ecc2k130
# The pinned CUDA 13.3 compiler from NVIDIA's pip wheels, as CI and the
# release build use it (scripts/fetch_cuda.sh).
RUN scripts/fetch_cuda.sh /opt/cuda
ARG ARCH="-gencode arch=compute_80,code=sm_80 -gencode arch=compute_86,code=sm_86 \
-gencode arch=compute_89,code=sm_89 -gencode arch=compute_90,code=sm_90 \
-gencode arch=compute_100,code=sm_100 -gencode arch=compute_120,code=sm_120 \
-gencode arch=compute_120,code=compute_120"
RUN make build/sigma/hosttest \
    && build/sigma/hosttest 64 tests/campaign-kat.hex \
    && make gpu WALK=sigma NVCC=/opt/cuda/bin/nvcc ARCH="$ARCH" \
    && build/ec2k-gpu check --kat tests/campaign-kat.hex \
    && if ldd build/ec2k-gpu | grep -q libcudart; then \
           echo "ec2k-gpu links a shared CUDA runtime" >&2; exit 1; \
       fi

# ---- runtime ------------------------------------------------------------------
FROM debian:${DEBIAN}-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 65532 --no-create-home --shell /usr/sbin/nologin gpuhealth
COPY --from=build /src/ecc2k130/build/ec2k-gpu /usr/local/bin/ec2k-gpu
COPY --from=build /src/ecc2k130/tests/campaign-kat.hex /usr/local/share/gpu-health/
COPY --chmod=0755 deploy/gpu-health/gpu_health.py /usr/local/bin/gpu-health
COPY deploy/gpu-health/baselines.json /etc/gpu-health/baselines.json
# compute for the walk, utility for nvidia-smi's telemetry.  The image does not
# set NVIDIA_VISIBLE_DEVICES: which GPUs it sees is the runtime's decision
# (docker --gpus, or the Kubernetes device plugin for nvidia.com/gpu).
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    GPU_HEALTH_BASELINES=/etc/gpu-health/baselines.json \
    PYTHONDONTWRITEBYTECODE=1
LABEL org.opencontainers.image.title="gpu-health" \
      org.opencontainers.image.description="GPU health check: a self-verifying ECC2K-130 Pollard rho load" \
      org.opencontainers.image.source="https://github.com/aburan28/cryptanalysis"
USER 65532:65532
ENTRYPOINT ["python3", "/usr/local/bin/gpu-health"]
