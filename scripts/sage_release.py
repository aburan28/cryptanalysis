#!/usr/bin/env python3
"""Apply, verify, build, and package the pinned binary-curve Sage patch stack."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "sage-release-manifest.json"


def run(*args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sage_path(value):
    if value:
        return Path(value).expanduser().resolve()
    local = ROOT / "third_party" / "sage-binary"
    if local.exists():
        return local
    # An isolated Git worktree still shares the main checkout's local Sage.
    common = Path(output("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=ROOT))
    return common.parent / "third_party" / "sage-binary"


def sage_env():
    env = os.environ.copy()
    if not env.get("DOT_SAGE"):
        cache = ROOT / "build" / "sage-dot-sage"
        cache.mkdir(parents=True, exist_ok=True)
        env["DOT_SAGE"] = str(cache)
    return env


def verify_revision(sage, manifest):
    revision = output("git", "rev-parse", "HEAD", cwd=sage)
    if revision != manifest["sage_commit"]:
        raise SystemExit(f"Sage revision {revision} does not match pinned {manifest['sage_commit']}")


def verify_sources(sage, manifest):
    mismatches = [name for name, expected in manifest["files"].items()
                  if not (sage / name).is_file() or digest(sage / name) != expected]
    if mismatches:
        raise SystemExit("Sage source does not match release stack: " + ", ".join(mismatches))
    print(f"verified {len(manifest['files'])} Sage source files at {sage}")


def verify_installed(sage, manifest):
    """Fail before an experiment if Sage still imports old installed modules."""
    packages = sorted((sage / "local" / "var" / "lib" / "sage").glob(
        "venv-python*/lib/python*/site-packages/sage/schemes/elliptic_curves"))
    if len(packages) != 1:
        raise SystemExit(f"expected one installed Sage elliptic-curves package, found {len(packages)}")
    package = packages[0]
    names = ("binary_batch.py", "binary_hardware.py", "ell_point.py", "hom_frobenius.py")
    stale = [name for name in names if not (package / name).is_file() or
             digest(package / name) != manifest["files"]["src/sage/schemes/elliptic_curves/" + name]]
    if stale:
        raise SystemExit("rebuild Sage before running experiments; stale installed modules: " +
                         ", ".join(stale))
    extensions = ("binary_batch_ntl.*.so", "binary_hardware_codec.*.so")
    missing = [pattern for pattern in extensions if not list(package.glob(pattern))]
    if not any(path.suffix in (".so", ".dylib", ".dll")
               for path in package.glob("_binary_hardware_native.*")):
        missing.append("_binary_hardware_native")
    if missing:
        raise SystemExit("rebuild Sage before running experiments; missing native modules: " +
                         ", ".join(missing))
    print(f"verified installed Sage elliptic-curve modules at {package}")


def patch_args(item):
    patch = ROOT / item["path"]
    if digest(patch) != item["sha256"]:
        raise SystemExit(f"patch digest changed: {patch}")
    return (["--unidiff-zero"] if item.get("unidiff_zero") else []) + [str(patch)]


def preflight(sage, manifest):
    """Reconstruct the complete stack from pinned upstream blobs before edits."""
    targets = list(manifest["files"])
    tracked = [name for name in targets if subprocess.run(
        ["git", "cat-file", "-e", "HEAD:" + name], cwd=sage,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0]
    with tempfile.TemporaryDirectory(prefix="sage-release-check-") as directory:
        archive = subprocess.check_output(["git", "archive", "HEAD", "--", *tracked], cwd=sage)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for entry in tar.getmembers():
                if not (entry.isfile() or entry.isdir()) or entry.name.startswith("/") or ".." in Path(entry.name).parts:
                    raise SystemExit("unexpected file in pinned Sage archive")
                destination = Path(directory) / entry.name
                if entry.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(tar.extractfile(entry).read())
        for item in manifest["patches"]:
            run("git", "apply", "--check", *patch_args(item), cwd=directory)
            run("git", "apply", *patch_args(item), cwd=directory)
        verify_sources(Path(directory), manifest)


def apply_stack(sage, manifest):
    verify_revision(sage, manifest)
    preflight(sage, manifest)
    if all((sage / name).is_file() and digest(sage / name) == expected
           for name, expected in manifest["files"].items()):
        print("release patch stack is already applied")
        return
    targets = list(manifest["files"])
    dirty = output("git", "diff", "--name-only", "HEAD", "--", *targets, cwd=sage)
    present = [name for name in targets if (sage / name).exists() and
               subprocess.run(["git", "cat-file", "-e", "HEAD:" + name], cwd=sage,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0]
    if dirty or present:
        raise SystemExit("refusing to apply over modified Sage patch targets")
    for item in manifest["patches"]:
        run("git", "apply", "--check", *patch_args(item), cwd=sage)
        run("git", "apply", *patch_args(item), cwd=sage)
    verify_sources(sage, manifest)


def bundle(manifest, output_dir, version):
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"cryptanalysis-sage-{version}-source"
    archive = output_dir / (name + ".tar.gz")
    paths = ["scripts/sage_release.py", "scripts/sage-release-manifest.json",
             "scripts/sage_release_smoke.py", "docs/SAGE_RELEASE.md"]
    paths += [item["path"] for item in manifest["patches"]]
    with tarfile.open(archive, "w:gz") as tar:
        for path in paths:
            tar.add(ROOT / path, arcname=name + "/" + path)
    (output_dir / (archive.name + ".sha256")).write_text(
        f"{digest(archive)}  {archive.name}\n")
    print(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["apply", "verify", "verify-installed", "verify-stack", "build", "smoke", "bundle", "run"])
    parser.add_argument("--sage", help="path to the pinned Sage source checkout")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default="dev")
    parser.add_argument("--jobs", type=int, default=2)
    args, remainder = parser.parse_known_args()
    manifest = json.loads(MANIFEST.read_text())
    if args.command == "bundle":
        bundle(manifest, args.out, args.version)
        return
    sage = sage_path(args.sage)
    if not sage.is_dir():
        raise SystemExit(f"Sage checkout does not exist: {sage}")
    if args.command == "apply":
        apply_stack(sage, manifest)
        return
    if args.command == "verify-stack":
        verify_revision(sage, manifest)
        preflight(sage, manifest)
        return
    verify_revision(sage, manifest)
    verify_sources(sage, manifest)
    if args.command in ("verify-installed", "smoke", "run"):
        verify_installed(sage, manifest)
    if args.command == "build":
        if args.jobs < 1:
            raise SystemExit("--jobs must be positive")
        run("make", f"-j{args.jobs}", cwd=sage)
        verify_installed(sage, manifest)
        run(str(sage / "sage"), "-python", str(ROOT / "scripts" / "sage_release_smoke.py"), cwd=sage, env=sage_env())
    elif args.command == "smoke":
        run(str(sage / "sage"), "-python", str(ROOT / "scripts" / "sage_release_smoke.py"), cwd=sage, env=sage_env())
    elif args.command == "run":
        if remainder and remainder[0] == "--":
            remainder = remainder[1:]
        if not remainder:
            raise SystemExit("run requires Sage arguments after --")
        os.execve(str(sage / "sage"), [str(sage / "sage"), *remainder], sage_env())


if __name__ == "__main__":
    main()
