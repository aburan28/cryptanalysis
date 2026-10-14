#!/usr/bin/env python3
"""Build the two public images from a minimal, source-bound Docker context."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[3]


def stage(source: Path, context: Path) -> None:
    target = context / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "build"))
    else:
        shutil.copy2(source, target)


def build(kind: str, tag: str, platform: str) -> None:
    public = ROOT / "ecc2k130/runner/public"
    with tempfile.TemporaryDirectory(prefix="ecc2k130-image-") as folder:
        context = Path(folder)
        inputs = [public / f"Dockerfile.{kind}"]
        if kind == "worker":
            inputs.extend([ROOT / "ecc2k130/Makefile", ROOT / "ecc2k130/src",
                           ROOT / "ecc2k130/include", ROOT / "ecc2k130/generated",
                           ROOT / "ecc2k130/tests/campaign-kat.hex",
                           ROOT / "fpga/model/ecc2k130.c", ROOT / "fpga/model/ecc2k130.h",
                           public / "client.py", public / "protocol.py"])
        else:
            inputs.extend([public / "server.py", public / "ingest.py",
                           public / "check_rds.py",
                           public / "protocol.py", public / "seed_registry.py",
                           ROOT / "ecc2k130/runner/aws/rds_gpu.py"])
        for item in inputs:
            stage(item, context)
        subprocess.run(["docker", "build", "--platform", platform,
                        "-f", str((context / public.relative_to(ROOT) / f"Dockerfile.{kind}")),
                        "-t", tag, str(context)], check=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("worker", "gateway"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--platform", default="linux/amd64")
    args = parser.parse_args(argv)
    build(args.kind, args.tag, args.platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
