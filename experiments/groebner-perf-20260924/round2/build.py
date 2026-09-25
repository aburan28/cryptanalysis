"""Build local controls/prototypes and record content-bound reconstruction recipes."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PREFIX = Path("/var/tmp/sage-10.9-current/local")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts-only", action="store_true")
    args = parser.parse_args()
    (HERE / "build").mkdir(exist_ok=True)
    shared = "boolean-dual.dylib" if sys.platform == "darwin" else "boolean-dual.so"
    common = ["clang++", "-O3", "-std=c++17"]
    m4ri = [f"-I{PREFIX}/include", f"-L{PREFIX}/lib", "-lm4ri", f"-Wl,-rpath,{PREFIX}/lib"]
    jobs = [
        ("boolean-dual", common + [str(HERE / "boolean_dual.cpp")]),
        (shared, common + (["-dynamiclib"] if sys.platform == "darwin" else ["-shared", "-fPIC"]) +
         ["-DBOOLEAN_DUAL_LIBRARY", "-DBOOLEAN_DUAL_NO_MAIN", str(HERE / "boolean_dual.cpp")]),
        ("boolean-dual-ubsan", ["clang++", "-O2", "-g", "-std=c++17", "-fsanitize=undefined",
                                "-fno-sanitize-recover=all", str(HERE / "boolean_dual.cpp")]),
        ("round1-m4ri", common + [str(HERE / "baseline/boolean_f5b_m4ri.cpp")] + m4ri),
        ("batch-round1", common + ["-DHYBRID", f'-DSOLVER_SOURCE="{HERE}/baseline/boolean_f5b_m4ri.cpp"',
                                   str(HERE.parent / "batch_bench.cpp")] + m4ri),
    ]
    if sys.platform == "darwin":
        jobs.append(("batch-rref", common + ["-fobjc-arc", "-framework", "Foundation", "-framework", "Metal",
                                              str(HERE / "batch_rref.mm")] + m4ri))
    recipes = []
    for name, command in jobs:
        target = HERE / "build" / name
        command += ["-o", str(target)]
        if not args.receipts_only:
            subprocess.run(command, check=True)
        recipes.append({"binary": str(target), "sha256": sha(target) if target.exists() else None,
                        "command": command})
    sources = [p for p in HERE.rglob("*") if p.suffix in (".cpp", ".mm", ".metal", ".py", ".rs")
               and "build" not in p.parts]
    sources += [HERE.parent / "fixtures.json", HERE / "matrices.json", HERE.parent / "batch_bench.cpp",
                HERE / "external-fixtures.json", HERE / "scaling-fixtures.json"]
    sources += [HERE.parent.parent / "pdp-scaling" / p for p in
                ["boolean_basis.py", "boolean_m4ri_runner.py", "boolean_native_runner.py", "test_boolean_basis.py"]]
    sources += [Path("/Volumes/SSD990/crypto/research/gbrl") / p for p in
                ["src/f4.rs", "examples/f4_preprocess_round2.rs"]]
    result = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "platform": platform.platform(), "compiler": subprocess.check_output(["clang++", "--version"], text=True),
              "recipes": recipes, "sources_sha256": {str(p): sha(p) for p in sources if p.is_file()},
              "library_sha256": {str(p): sha(p) for p in (PREFIX / "lib").glob("libm4ri.*") if p.is_file()},
              "external_solver": {"sage_version_source": str(PREFIX / "lib/python3.14/site-packages/sage/version.py"),
                                  "sage_version": "10.9", "polybori_options": "Sage Boolean ideal groebner_basis defaults"},
              "scope": "GB and internal Macaulay PDP stage diagnostics; no complete IC pipeline candidate or DLP total"}
    (HERE / "results/build-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Recorded", len(recipes), "builds")


if __name__ == "__main__":
    main()
