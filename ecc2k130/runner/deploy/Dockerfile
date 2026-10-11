FROM nvidia/cuda:13.3.1-devel-ubuntu24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install -y --no-install-recommends \
    build-essential python3 python3-venv ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 AWS_EC2_METADATA_DISABLED=true
WORKDIR /opt/ecc2k130
RUN curl --fail --show-error --location \
    https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
    -o /opt/ecc2k130/global-bundle.pem
ENV PGSSLROOTCERT=/opt/ecc2k130/global-bundle.pem
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY Makefile ./
COPY src/ src/
COPY include/ include/
COPY generated/ generated/
COPY codegen/ codegen/
# Preserve the legacy Frobenius walk used by the shared ecc2k-130 campaign.
ARG CUDA_ARCH=120
RUN test "$CUDA_ARCH" = "120" && make gpu-production
COPY aws/worker.py aws/rds_gpu.py aws/rds_network.py aws/
COPY cloud.py build.json ./
COPY aws/campaign.json aws/campaign.json
ENV ECC_ROOT=/workspace/ecc2k130 ECC_CLIENT=/opt/ecc2k130/ecc2k130
ENV ECC_PREFIX=campaigns/ecc2k130-frobenius32-120k-v1
STOPSIGNAL SIGTERM
# Exec form delivers Pod shutdown directly to the supervisor.
ENTRYPOINT []
CMD ["python3", "/opt/ecc2k130/cloud.py", "run", "--seconds", "82800"]
