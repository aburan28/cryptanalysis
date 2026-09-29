"""Standalone Modal image build function, imported inside the builder."""


def build_sage(stage: str) -> None:
    import subprocess
    subprocess.run(["bash", "/opt/modal/build_sage_linux.sh", stage], check=True)


def build_sage_packages(packages: tuple[str, ...]) -> None:
    """Checkpoint a group of Sage packages before the full local build."""
    import subprocess

    for package in packages:
        subprocess.run(["make", "-j4", package], cwd="/opt/sage-binary", check=True)
