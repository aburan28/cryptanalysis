"""Build opt-in bitset-reuse F4 from a pinned initial-batch source."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from generate import ENGINE_SHA256, HERE, bitset_engine


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path)
    args = parser.parse_args()
    root = HERE.parents[2]
    for path in HERE.glob("*.py"):
        relative = path.relative_to(root)
        assert path.read_bytes() == subprocess.check_output(
            ["git", "show", "HEAD:" + str(relative)], cwd=root)
    reference = (args.reference_root or root).resolve()
    earlier = HERE.parent / "round118"
    engine = earlier / "build/engine.inc"
    if not engine.exists():
        command = [sys.executable, str(earlier / "build.py")]
        if args.reference_root is not None:
            command += ["--reference-root", str(reference)]
        subprocess.run(command, check=True)
    assert sha(engine) == ENGINE_SHA256
    prior = json.loads((earlier / "build/receipt.json").read_text())
    assert prior["generated_engine_sha256"] == ENGINE_SHA256
    for name, digest in prior["binaries"].items():
        assert sha(earlier / "build" / name) == digest
    module_path = HERE.parent / "round113/generate.py"
    spec = importlib.util.spec_from_file_location("seeded_phase_source117", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = HERE / "build"
    output.mkdir(exist_ok=True)
    generated_engine = output / "engine.inc"
    generated_engine.write_text(bitset_engine(engine.read_text()))
    generated_seeded = output / "seeded_phases.cpp"
    generated_seeded.write_text(module.generate())
    compiler = os.environ.get("CXX", "clang++")
    shared = ["-dynamiclib"] if sys.platform == "darwin" else ["-shared", "-fPIC"]
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    commands, binaries = [], {}
    for tag, flags in (("", ["-O3"]), ("-ubsan", ["-O1", "-g", "-fsanitize=undefined",
                                           "-fsanitize-undefined-trap-on-error",
                                           "-fno-sanitize-recover=all"])):
        binary = output / ("seeded_bitset" + tag + suffix)
        command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", *flags,
                   *shared, "-I", str(output), "-I", str(HERE.parent / "round11"),
                   "-I", str(HERE.parent / "round55"), "-I", str(HERE.parent / "round110"),
                   "-I", str(HERE.parent / "round113"), "-DPERSISTENT_ORDER=1",
                   "-DPIVOT_KEYS=1", "-DINDEXED_REDUCERS=0", str(generated_seeded),
                   "-o", str(binary)]
        subprocess.run(command, check=True)
        commands.append(command)
        binaries[binary.name] = sha(binary)
    receipt = dict(schema="f4-row-bitset-build/1",
                   source_commit=subprocess.check_output(
                       ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                   sources={p.name: sha(p) for p in HERE.glob("*.py")},
                   reference_root=str(reference), previous_build=prior,
                   previous_engine_sha256=sha(engine),
                   generated_engine_sha256=sha(generated_engine),
                   generated_seeded_sha256=sha(generated_seeded),
                   compiler=subprocess.check_output([compiler, "--version"], text=True),
                   architecture=platform.machine(), platform=platform.platform(),
                   commands=commands, binaries=binaries, timing_eligible=False,
                   qualified_speedup=None)
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("F4_BITSET_BUILD_PASS", len(binaries), flush=True)


if __name__ == "__main__":
    main()
