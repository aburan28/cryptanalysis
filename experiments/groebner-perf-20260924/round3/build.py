"""Build isolated verifier libraries, recording the exact source/compiler."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "pdp-scaling/boolean_certificate.cpp"


def main():
    (HERE / "build").mkdir(exist_ok=True)
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    records = []
    for variant, flags in [("", ["-O3"]), ("-ubsan", ["-O1", "-g", "-fsanitize=undefined", "-fno-sanitize-recover=all"])]:
        output = HERE / "build" / ("boolean-certificate"+variant+suffix)
        command = ["clang++", "-std=c++17", *flags, "-Wall", "-Wextra", "-Werror",
                   "-dynamiclib" if sys.platform == "darwin" else "-shared", "-fPIC", str(SOURCE), "-o", str(output)]
        subprocess.run(command, check=True)
        records.append({"command": command, "binary_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    if sys.platform == "darwin":
        prefix = Path("/var/tmp/sage-10.9-current/local")
        for name, source in [("tiled-rref", HERE / "tiled_rref.mm"),
                             ("capture-m4ri", HERE.parent / "round2/capture/boolean_f5b_m4ri.cpp")]:
            output = HERE / "build" / name
            command = ["clang++", "-O3", "-std=c++17", str(source),
                       f"-I{prefix}/include", f"-L{prefix}/lib", "-lm4ri", f"-Wl,-rpath,{prefix}/lib", "-o", str(output)]
            if source.suffix == ".mm":
                command += ["-fobjc-arc", "-framework", "Foundation", "-framework", "Metal"]
            subprocess.run(command, check=True)
            records.append({"command": command, "binary_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    report = {"source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "builds": records,
              "compiler": subprocess.check_output(["clang++", "--version"], text=True)}
    (HERE / "results/build-manifest.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
