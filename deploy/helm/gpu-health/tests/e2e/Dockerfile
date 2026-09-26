# The chart's end-to-end test image: the real gpu-health image plus the
# scripted ec2k-gpu and nvidia-smi of deploy/gpu-health/tests/fakes, so that
# the injected check can run on a kind node, which has no GPU; a stand-in PCI
# bus with two NVIDIA GPUs (and an NVSwitch, which does not count); and
# stand-in /proc files (another boot id and uptime) for the steps that play a
# reboot and a node long in service.  Built by run.sh from the repository root.
ARG BASE=gpu-health:ci
FROM ${BASE}
COPY deploy/gpu-health/tests/fakes/ /fakes/
COPY deploy/helm/gpu-health/tests/e2e/scenarios/ /fakes/scenarios/
COPY deploy/helm/gpu-health/tests/e2e/proc/ /fakes/proc/
COPY deploy/helm/gpu-health/tests/e2e/pci/ /fakes/pci/
