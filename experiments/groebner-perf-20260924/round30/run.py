"""Build and run a bounded, source-bound Metal RREF experiment."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = [HERE / name for name in ("row_map.metal", "row_map.mm", "run.py", "audit.py")]
SOURCES += [HERE.parent / "round29" / name for name in ("active_panel.metal", "active_rref.mm")]
SOURCES += [HERE.parent / "round7" / name for name in ("local_panel.metal", "local_rref.mm")]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--m4ri-prefix", required=True, type=Path)
    parser.add_argument("--threads", type=int, choices=(256, 512, 1024), default=512)
    parser.add_argument("--mode", choices=("correctness", "all"), default="all")
    parser.add_argument("--no-word-skip", action="store_true", help="ablation: test each column separately")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 600:
        parser.error("timeout must be finite and in (0,600]")
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": "row-map-receipt/1", "status": "building", "start_unix": time.time(),
        "platform": platform.platform(), "architecture": platform.machine(), "python": sys.version,
        "logical_cpus": os.cpu_count(), "load_start": os.getloadavg(), "pivot_threads": args.threads,
        "mode": args.mode, "word_skip": not args.no_word_skip, "previous_pivot_threads": 512, "previous_indirect": False, "scope": "single-matrix RREF; no full polynomial query or IC timing",
        "candidate_id": None, "IC_online_ms": None, "rho_online_ms": None,
        "timeout_seconds_per_command": args.timeout, "runs": {},
    }

    def save():
        (dest / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    save()
    try:
        receipt["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        receipt["cpu"] = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        receipt["compiler"] = subprocess.check_output(["clang++", "--version"], text=True)
        receipt["sources"] = {}
        for source in SOURCES:
            relative = source.relative_to(HERE.parent)
            target = dest / "sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            receipt["sources"][str(relative)] = sha(target)
        frozen = (dest / "sources/round29/active_rref.mm").read_text()
        marker = "int main(int argc,char**argv)"
        if frozen.count(marker) != 1:
            raise ValueError("unexpected frozen baseline entrypoint")
        generated = dest / "sources/round29/active_rref_library.mm"
        generated.write_text(frozen.replace(marker, "int unused_round29_main(int argc,char**argv)"))
        receipt["generated_library_sha256"] = sha(generated)
        library = args.m4ri_prefix.resolve() / "lib/libm4ri.dylib"
        receipt["m4ri_library"] = str(library.resolve())
        receipt["m4ri_sha256"] = sha(library)
        matrix_gz = HERE.parent / "round3/matrices.json.gz"
        matrices = dest / "matrices.json"
        matrices.write_bytes(gzip.decompress(matrix_gz.read_bytes()))
        receipt["matrix_sha256"] = sha(matrices)
        receipt["matrix_gz_sha256"] = sha(matrix_gz)
        binary = dest / "row-map"
        command = ["clang++", "-O3", "-std=c++17", "-fobjc-arc", "-DACTIVE_THREADS=512", "-DACTIVE_INDIRECT=0", f"-DMAP_THREADS={args.threads}",
                   f"-DMAP_SKIP_WORDS={int(not args.no_word_skip)}",
                   str(dest / "sources/round30/row_map.mm"),
                   "-I" + str(args.m4ri_prefix.resolve() / "include"),
                   "-L" + str(args.m4ri_prefix.resolve() / "lib"), "-lm4ri",
                   "-framework", "Foundation", "-framework", "Metal", "-o", str(binary)]
        receipt["compile_command"] = command
        save()
        with (dest / "build.log").open("x") as log:
            built = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        receipt["compile_returncode"] = built.returncode
        if built.returncode:
            receipt["status"] = "build_failed"
            return 1
        receipt["binary_sha256"] = sha(binary)
        receipt["linked_libraries"] = subprocess.check_output(["otool", "-L", str(binary)], text=True)
        receipt["status"] = "running"
        save()
        for mode in (["correctness", "measure"] if args.mode == "all" else ["correctness"]):
            command = [str(binary), str(dest / "sources/round7/local_panel.metal"),
                       str(dest / "sources/round29/active_panel.metal"),
                       str(dest / "sources/round30/row_map.metal"), str(matrices), mode]
            run = {"command": command, "start_unix": time.time(), "load_start": os.getloadavg(), "status": "running"}
            receipt["runs"][mode] = run
            save()
            with (dest / f"{mode}.json").open("x") as out, (dest / f"{mode}.log").open("x") as err:
                result = subprocess.run(command, stdout=out, stderr=err, timeout=args.timeout)
            run.update(returncode=result.returncode, end_unix=time.time(), load_end=os.getloadavg(),
                       report_sha256=sha(dest / f"{mode}.json"), status="PASS" if result.returncode == 0 else "failed")
            if result.returncode:
                receipt["status"] = "failed"
                return 1
            report = json.loads((dest / f"{mode}.json").read_text())
            if report.get("exact_rank_and_rref") is not True:
                raise ValueError("missing exact-output qualification")
            actual_library = Path(report["m4ri_library"])
            run["loaded_m4ri_sha256"] = sha(actual_library)
            if run["loaded_m4ri_sha256"] != receipt["m4ri_sha256"]:
                raise ValueError("loaded M4RI differs from the recorded library")
            run["checked_matrices"] = report["checked_matrices"]
            save()
        receipt["status"] = "PASS"
        return 0
    except subprocess.TimeoutExpired as exc:
        receipt["status"] = "timeout"
        receipt["error"] = str(exc)
        return 1
    except Exception as exc:
        receipt["status"] = "error"
        receipt["error"] = str(exc)
        return 1
    finally:
        receipt["end_unix"] = time.time()
        receipt["load_end"] = os.getloadavg()
        save()
        print(json.dumps({"status": receipt["status"], "receipt": str(dest / "receipt.json")}))


if __name__ == "__main__":
    raise SystemExit(main())
