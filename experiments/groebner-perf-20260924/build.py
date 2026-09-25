#!/usr/bin/env python3
"""Rebuild frozen controls and candidates; retain commands and SHA256 receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "pdp-scaling"
sys.path.insert(0, str(SOURCE))
from boolean_m4ri_runner import _m4ri_prefix


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts-only", action="store_true",
                        help="record existing builds without recompiling")
    args = parser.parse_args()
    compiler = os.environ.get("CXX", "clang++")
    prefix = _m4ri_prefix()
    (HERE / "build").mkdir(exist_ok=True)
    jobs = []
    configurations = [("original", HERE / "baseline", HERE / "baseline", "native", "m4ri"),
                      ("corrected", HERE / "corrected", HERE / "build", "corrected-native", "corrected-m4ri"),
                      ("optimized", SOURCE, HERE / "build", "cursor-native", "screened-m4ri")]
    for label, folder, output, native_name, matrix_name in configurations:
        for backend, filename in [("native", native_name), ("m4ri", matrix_name)]:
            source = folder / f"boolean_f5b_{backend}.cpp"
            for batch in ([False] if label == "original" else [False, True]):
                target = HERE / "build" / f"batch-{label}-{backend}" if batch else output / filename
                command = [compiler, "-O3", "-std=c++17"]
                inputs = [source]
                if backend == "m4ri":
                    inputs.append(folder / "boolean_f5b_native.cpp")
                if batch:
                    command += [f'-DSOLVER_SOURCE="{source}"', str(HERE / "batch_bench.cpp")]
                    inputs.append(HERE / "batch_bench.cpp")
                    if backend == "m4ri": command += ["-DHYBRID"]
                else:
                    command += [str(source)]
                if backend == "m4ri":
                    command += [f"-I{prefix / 'include'}", f"-L{prefix / 'lib'}", "-lm4ri",
                                f"-Wl,-rpath,{prefix / 'lib'}"]
                command += ["-o", str(target)]
                jobs.append((target, command, inputs))
    if sys.platform == "darwin":
        target = HERE / "build" / "metal-panel-vector"
        source = HERE / "metal_panel.mm"
        jobs.append((target, [compiler, "-O3", "-std=c++17", "-fobjc-arc",
                             "-framework", "Foundation", "-framework", "Metal",
                             str(source), "-o", str(target)], [source, HERE / "panel.metal"]))
    manifest = {"platform": platform.platform(), "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
                "compiler": subprocess.check_output([compiler,"--version"],text=True),
                "recipes": [], "external_library_instrumented": False,
                "note": "receipts-only records reconstruction recipes for existing builds; benchmark files bind measured binary hashes"}
    for binary, command, inputs in jobs:
        if not args.receipts_only:
            subprocess.run(command, check=True, capture_output=True)
        manifest["recipes"].append({"command": command, "binary": str(binary),
                                    "binary_sha256": sha(binary) if binary.exists() else None,
                                    "inputs": {str(p):sha(p) for p in inputs}})
    manifest["m4ri_libraries"] = {str(p):sha(p) for p in sorted((prefix / "lib").glob("libm4ri.*")) if p.is_file()}
    manifest["corpus_sha256"] = sha(HERE / "fixtures.json")
    manifest["source_files"] = {str(p):sha(p) for p in [SOURCE / "boolean_f5b.py",
                                 SOURCE / "boolean_basis.py", SOURCE / "boolean_m4ri_runner.py",
                                 SOURCE / "boolean_native_runner.py", HERE / "benchmark.py",
                                 HERE / "validate.py", HERE / "query_benchmark.py",
                                 Path("/Volumes/SSD990/crypto/research/gbrl/src/f4.rs"),
                                 Path("/Volumes/SSD990/crypto/research/gbrl/examples/f4_preprocess_bench.rs")] if p.exists()}
    (HERE / "results" / "build-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"Recorded {len(jobs)} build recipes")


if __name__ == "__main__":
    main()
