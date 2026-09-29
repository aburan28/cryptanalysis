"""Standalone Modal image build function, imported inside the builder."""


def build_sage() -> None:
    import subprocess
    subprocess.run(["bash", "/opt/modal/build_sage_linux.sh"], check=True)
