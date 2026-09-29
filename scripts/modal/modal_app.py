"""Build the Linux Sage fork once, then launch independent Modal calculations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import modal
from build_image_step import build_sage, build_sage_packages


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / ".build/sage-source.tar.gz"
APP_NAME = "cryptanalysis-sage-jobs"
VOLUME_NAME = "cryptanalysis-sage-results"


# The source archive comes from package_sage_source.sh. No macOS binaries or
# local credentials enter this image. The long source build is cached by Modal.
image = (
    modal.Image.from_registry("ubuntu:24.04", add_python="3.12")
    .apt_install(
        "autoconf", "automake", "bc", "binutils", "bison", "build-essential",
        "bzip2", "ca-certificates",
        "cmake", "cryptominisat", "curl", "flex", "gfortran", "git",
        "libboost-graph-dev", "libbz2-dev", "libffi-dev", "libgmp-dev", "liblapack-dev",
        "liblzma-dev", "libm4ri-dev", "libmpc-dev", "libmpfr-dev", "libntl-dev",
        "libopenblas-dev", "libreadline-dev", "libsqlite3-dev", "libssl-dev",
        "libtool", "m4", "ninja-build", "patch", "perl", "pkg-config",
        "python3-dev", "python3-pip", "python3-setuptools", "python3-venv",
        "redis-server", "texinfo", "xz-utils", "zlib1g-dev", "zstd",
    )
    .run_commands("curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.94.1")
    .env({"PATH": "/root/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
    .add_local_file(ARCHIVE, "/opt/modal/sage-source.tar.gz", copy=True)
    .add_local_file(HERE / "build_sage_linux.sh", "/opt/modal/build_sage_linux.sh", copy=True)
    .run_function(build_sage, args=("prepare",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("flint",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("gf2x",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("highs",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage_packages, args=((
        "libpng", "cddlib", "curl", "libatomic_ops", "info",
        "primesieve", "givaro", "gsl",
    ),), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage_packages, args=((
        "fplll", "freetype", "gap", "gengetopt", "gfan", "glpk",
        "libbraiding", "libgd", "mpfi", "nauty", "palp",
        "planarity", "ppl", "primecount",
    ),), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("local",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("venv",), cpu=8, memory=32768, timeout=86400)
    .run_function(build_sage, args=("verify",), cpu=8, memory=32768, timeout=86400)
    .add_local_file(HERE / "remote_sage.sh", "/opt/modal/remote_sage.sh", copy=True)
    .add_local_file(HERE / "accept_linux_runtime.py", "/opt/modal/accept_linux_runtime.py", copy=True)
    .add_local_file(HERE / "run_job.py", "/opt/modal/run_job.py", copy=True)
    .add_local_file(HERE / "validators/runtime_check.py",
                    "/opt/modal/runtime_check.py", copy=True)
    .add_local_file(HERE / "validators/validate_compatibility.py",
                    "/opt/modal/validate_compatibility.py", copy=True)
    .add_local_file(HERE / "validators/test_portability.py",
                    "/opt/modal/test_portability.py", copy=True)
    .add_local_file(HERE / "validators/test_hardware.py",
                    "/opt/modal/test_hardware.py", copy=True)
    .add_local_file(HERE / "validators/load_hardware.py",
                    "/opt/modal/load_hardware.py", copy=True)
)


def launch(revision: str, script: str, job_id: str, args_json: str = "[]",
           cpu: float = 8.0, memory_mb: int = 32768, timeout_s: int = 86400) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("revision must be a full lowercase commit SHA")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,63}", job_id) is None:
        raise ValueError("job_id must be 1-63 letters, digits, underscores, or dashes")
    relative_script = Path(script)
    if relative_script.is_absolute() or ".." in relative_script.parts or relative_script.suffix not in (".py", ".sage"):
        raise ValueError("script must be a repository-relative .py or .sage path")
    arguments = json.loads(args_json)
    if not isinstance(arguments, list) or not all(isinstance(x, str) for x in arguments):
        raise ValueError("args_json must be a JSON list of strings")
    if not 1 <= timeout_s <= 86400:
        raise ValueError("timeout_s must be between 1 and 86400")
    if cpu <= 0 or memory_mb < 1024:
        raise ValueError("cpu and memory_mb must be positive; memory_mb >= 1024")
    if not ARCHIVE.is_file():
        raise FileNotFoundError(f"run package_sage_source.sh first: {ARCHIVE}")
    app = modal.App.lookup(APP_NAME, create_if_missing=True)
    results = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    with modal.enable_output():
        built_image = image.build(app=app)
    sandbox = modal.Sandbox.create(
        "python3", "/opt/modal/run_job.py", "--revision", revision,
        "--script", script, "--job-id", job_id, "--args-json", json.dumps(arguments),
        app=app, image=built_image, name=job_id,
        cpu=cpu, memory=memory_mb, timeout=timeout_s,
        env={"MODAL_REQUESTED_CPU": str(cpu),
             "MODAL_REQUESTED_MEMORY_MB": str(memory_mb),
             "MODAL_REQUESTED_TIMEOUT_S": str(timeout_s)},
        volumes={"/results": results},
    )
    print(json.dumps({"sandbox_id": sandbox.object_id, "job_id": job_id,
                      "volume": VOLUME_NAME, "result_path": f"/{job_id}"}))
    sandbox.detach()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--script", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--args-json", default="[]")
    parser.add_argument("--cpu", type=float, default=8.0)
    parser.add_argument("--memory-mb", type=int, default=32768)
    parser.add_argument("--timeout-s", type=int, default=86400)
    args = parser.parse_args()
    launch(**vars(args))


if __name__ == "__main__":
    main()
