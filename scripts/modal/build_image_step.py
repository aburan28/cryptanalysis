"""Standalone Modal image build function, imported inside the builder."""


def build_sage(stage: str) -> None:
    import subprocess
    subprocess.run(["bash", "/opt/modal/build_sage_linux.sh", stage], check=True)
