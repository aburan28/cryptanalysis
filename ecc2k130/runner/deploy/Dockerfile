FROM nvidia/cuda:13.3.1-devel-ubuntu24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install -y --no-install-recommends \
    build-essential python3 python3-venv ca-certificates curl openssh-server \
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
# Preserve the legacy Frobenius walk used by the shared ecc2k-130 campaign,
# while shipping native cubins for every supported GPU family.  CUDA_ARCH is
# retained as a compatibility build argument for existing Modal launchers;
# ECC_CUDA_ARCHES controls the fat binary contents.
ARG CUDA_ARCH=120
ARG ECC_CUDA_ARCHES="80 86 89 90 100 120"
COPY deploy/build_production.sh deploy/entrypoint.sh deploy/start.sh deploy/
RUN chmod +x deploy/build_production.sh deploy/entrypoint.sh deploy/start.sh \
    && deploy/build_production.sh "$ECC_CUDA_ARCHES"
COPY aws/worker.py aws/rds_gpu.py aws/rds_network.py aws/
COPY cloud.py build.json ./
COPY aws/campaign.json aws/campaign.json
ENV ECC_ROOT=/workspace/ecc2k130 ECC_CLIENT=/opt/ecc2k130/ecc2k130
ENV ECC_PREFIX=campaigns/ecc2k130-frobenius32-120k-v1
ENV ECC_SUPPORTED_SMS="$ECC_CUDA_ARCHES" \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    CUDA_DEVICE_ORDER=PCI_BUS_ID
STOPSIGNAL SIGTERM
# Exec form delivers Pod shutdown directly to the supervisor.
ENTRYPOINT ["/opt/ecc2k130/deploy/start.sh"]
CMD ["python3", "/opt/ecc2k130/cloud.py", "run", "--seconds", "82800"]
