"""Pin a freshly built Linux Sage fork after checking its installed modules."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


ROOT = Path(sys.argv[1]).resolve()
SAGE = ROOT / "third_party/sage-binary"
OUT = ROOT / "experiments/sage-binary-arithmetic/runtime-current.json"
sys.path.insert(0, str(OUT.parent))
import runtime_check  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    path = Path(path)
    if path.is_relative_to(SAGE.resolve()):
        return str(Path("third_party/sage-binary") / path.relative_to(SAGE.resolve()))
    return str(path.relative_to(ROOT))


def main() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("Linux acceptance only")
    if Path(sys.prefix).resolve() != (SAGE / "local/var/lib/sage/venv-python3.12").resolve():
        # Do not guess the minor version; check that Sage selected its own
        # installed prefix, whatever compatible Python it used.
        if not Path(sys.prefix).resolve().is_relative_to((SAGE / "local").resolve()):
            raise RuntimeError(f"Sage Python is outside installation: {sys.prefix}")
    names = ("ell_point", "binary_batch", "binary_batch_ntl", "binary_hardware")
    modules = {}
    files = {}
    for name in names:
        qualified = "sage.schemes.elliptic_curves." + name
        module = importlib.import_module(qualified)
        installed = Path(module.__file__).resolve()
        if not installed.is_relative_to((SAGE / "local").resolve()):
            raise RuntimeError(f"module outside Sage install: {installed}")
        modules[qualified] = relative(installed)
        files[relative(installed)] = sha(installed)
        source = SAGE / "src/sage/schemes/elliptic_curves" / (name + (".pyx" if name == "binary_batch_ntl" else ".py"))
        if not source.is_file():
            raise RuntimeError(f"missing source: {source}")
        files[relative(source.resolve())] = sha(source)
        if installed.suffix == ".py" and sha(installed) != sha(source):
            raise RuntimeError(f"installed module differs from source: {name}")
    for item in (ROOT / "sage", ROOT / "experiments/sage-binary-arithmetic/runtime_check.py", SAGE / "src/bin/sage"):
        files[relative(item.resolve())] = sha(item)
    native = importlib.import_module("sage.schemes.elliptic_curves.binary_batch_ntl")
    dispatch = ["_pari_point", "_add_pairs"]
    if hasattr(native, "_from_pari_point"):
        dispatch.append("_from_pari_point")
    receipt = OUT.parent / "modal-linux-acceptance.json"
    receipt.write_text(json.dumps({
        "status": "PASS_LOCAL", "platform": platform.platform(),
        "sage_source_archive_sha256": os.environ.get("SAGE_SOURCE_SHA256"),
        "python": sys.executable, "modules": modules,
    }, indent=2, sort_keys=True) + "\n")
    files[relative(receipt)] = sha(receipt)
    manifest = {
        "schema": 1, "python_prefix": relative(Path(sys.prefix).resolve()),
        "features": ["modal-linux-batch"], "modules": modules,
        "native_dispatch": dispatch, "receipt": relative(receipt),
        "files": [{"path": k, "sha256": v} for k, v in sorted(files.items())],
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    runtime_check.probe(runtime_check.check(OUT), OUT)
    subprocess.run([str(ROOT / "sage"), "--runtime-info"], check=True)


if __name__ == "__main__":
    main()
