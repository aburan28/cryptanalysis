#!/usr/bin/env python3
"""Apply, verify, build, and package the pinned binary-curve Sage patch stack."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
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
    stamp = package / ".cryptanalysis-binary-manifest.json"
    if stamp.exists():
        record = json.loads(stamp.read_text())
        if record.get("schema") != "cryptanalysis-sage-binary/1" or record.get("source_manifest_sha256") != digest(MANIFEST):
            raise SystemExit("installed Sage accelerator manifest does not match this source stack")
        stale_binary = [name for name, expected in record.get("files", {}).items()
                        if not (package / name).is_file() or digest(package / name) != expected]
        if stale_binary or len(record.get("files", {})) != 7:
            raise SystemExit("installed Sage accelerator files differ from their binary manifest: " +
                             ", ".join(stale_binary))
    print(f"verified installed Sage elliptic-curve modules at {package}")
    return package


PY_MODULES = ("binary_batch.py", "binary_hardware.py", "ell_point.py", "hom_frobenius.py")
NATIVE_MODULES = ("binary_batch_ntl", "binary_hardware_codec", "_binary_hardware_native")


def binary_files(package):
    paths = [package / name for name in PY_MODULES]
    for stem in NATIVE_MODULES:
        matches = [p for p in package.glob(stem + ".*") if p.suffix in (".so", ".dylib")]
        if len(matches) != 1:
            raise SystemExit(f"expected exactly one installed {stem} native module, found {len(matches)}")
        paths.append(matches[0])
    return paths


def sage_abi(sage):
    script = ("import json,platform,sys,sysconfig; "
              "print(json.dumps({'python': list(sys.version_info[:2]), "
              "'extension_suffix': sysconfig.get_config_var('EXT_SUFFIX'), "
              "'machine': platform.machine(), 'system': platform.system()}))")
    return json.loads(output(str(sage / "sage"), "-python", "-c", script, cwd=sage))


def binary_bundle(sage, manifest, output_dir, version):
    """Package only the patched accelerator overlay, never Sage's nonrelocatable tree."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("the compiled Sage overlay currently supports macOS arm64 only")
    package = verify_installed(sage, manifest)
    abi = sage_abi(sage)
    files = binary_files(package)
    for path in files:
        if path.suffix == ".so" and not path.name.endswith(abi["extension_suffix"]):
            raise SystemExit(f"native module has the wrong Python ABI: {path.name}")
    name = f"cryptanalysis-sage-{version}-macos-arm64-py{''.join(map(str, abi['python']))}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / (name + ".tar.gz")
    record = {"schema": "cryptanalysis-sage-binary/1", "sage_commit": manifest["sage_commit"],
              "source_manifest_sha256": digest(MANIFEST), "abi": abi,
              "files": {p.name: digest(p) for p in files}}
    with tarfile.open(archive, "w:gz") as tar:
        data = (json.dumps(record, sort_keys=True, indent=2) + "\n").encode()
        info = tarfile.TarInfo(name + "/binary-manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        for path in files:
            tar.add(path, arcname=name + "/" + path.name)
    (output_dir / (archive.name + ".sha256")).write_text(f"{digest(archive)}  {archive.name}\n")
    print(archive)


def install_binary(sage, manifest, archive):
    """Install a checked overlay into a prebuilt, matching Sage checkout."""
    if not archive:
        raise SystemExit("install-binary requires --archive")
    verify_revision(sage, manifest)
    verify_sources(sage, manifest)
    package = sorted((sage / "local" / "var" / "lib" / "sage").glob(
        "venv-python*/lib/python*/site-packages/sage/schemes/elliptic_curves"))
    if len(package) != 1:
        raise SystemExit("install-binary requires one complete, prebuilt Sage installation")
    package = package[0]
    abi = sage_abi(sage)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if any(not m.isfile() for m in members):
            raise SystemExit("binary archive contains a non-file member")
        names = [Path(m.name).parts for m in members]
        if any(len(parts) != 2 or parts[0] != names[0][0] for parts in names):
            raise SystemExit("binary archive has an unexpected path")
        payload = {parts[1]: tar.extractfile(member).read() for parts, member in zip(names, members)}
    if "binary-manifest.json" not in payload:
        raise SystemExit("binary archive has no manifest")
    record = json.loads(payload.pop("binary-manifest.json"))
    if (record.get("schema") != "cryptanalysis-sage-binary/1" or
            record.get("sage_commit") != manifest["sage_commit"] or
            record.get("source_manifest_sha256") != digest(MANIFEST) or record.get("abi") != abi):
        raise SystemExit("binary archive does not match this Sage revision, source stack, or Python ABI")
    if set(payload) != set(record["files"]) or set(PY_MODULES) - set(payload) or len(payload) != 7:
        raise SystemExit("binary archive has an incomplete or unexpected module set")
    for name, data in payload.items():
        if Path(name).name != name or hashlib.sha256(data).hexdigest() != record["files"][name]:
            raise SystemExit(f"binary archive has an invalid file: {name}")
        if name.endswith(".so") and not name.endswith(abi["extension_suffix"]):
            raise SystemExit(f"binary module has the wrong Python ABI: {name}")
        if name in PY_MODULES and record["files"][name] != manifest["files"]["src/sage/schemes/elliptic_curves/" + name]:
            raise SystemExit(f"binary archive has stale Sage source: {name}")
    with tempfile.TemporaryDirectory(prefix="sage-binary-backup-") as backup:
        originals = {}
        stamp = package / ".cryptanalysis-binary-manifest.json"
        old_stamp = stamp.read_bytes() if stamp.exists() else None
        for name in payload:
            target = package / name
            originals[name] = target.exists()
            if target.exists():
                shutil.copy2(target, Path(backup) / name)
        try:
            for name, data in payload.items():
                (package / name).write_bytes(data)
            stamp.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
            verify_installed(sage, manifest)
            run(str(sage / "sage"), "-python", str(ROOT / "scripts" / "sage_release_smoke.py"),
                cwd=sage, env=sage_env())
        except BaseException:
            for name, existed in originals.items():
                target = package / name
                if existed:
                    shutil.copy2(Path(backup) / name, target)
                else:
                    target.unlink(missing_ok=True)
            if old_stamp is None:
                stamp.unlink(missing_ok=True)
            else:
                stamp.write_bytes(old_stamp)
            raise
    print(f"installed and smoke-tested Sage accelerator overlay at {package}")


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
    parser.add_argument("command", choices=["apply", "verify", "verify-installed", "verify-stack", "build", "smoke", "bundle", "pack-binary", "install-binary", "run"])
    parser.add_argument("--sage", help="path to the pinned Sage source checkout")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", default="dev")
    parser.add_argument("--archive", type=Path, help="compiled Sage accelerator archive to install")
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
    if args.command == "install-binary":
        install_binary(sage, manifest, args.archive)
        return
    if args.command == "verify-stack":
        verify_revision(sage, manifest)
        preflight(sage, manifest)
        return
    verify_revision(sage, manifest)
    verify_sources(sage, manifest)
    if args.command in ("verify-installed", "smoke", "run"):
        verify_installed(sage, manifest)
    if args.command == "pack-binary":
        binary_bundle(sage, manifest, args.out, args.version)
        return
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
