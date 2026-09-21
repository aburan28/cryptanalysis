"""Compare two Frobenius clients, including resume across block geometries.

Runs only local temporary walks; no campaign checkpoints or records are written.
Both binaries must have batch 16 and emit checkpoint v2 / gpu-packed32 records.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile


def corpus(path):
    data = path.read_bytes() if path.exists() else b""
    if len(data) % 32:
        raise AssertionError("partial distinguished-point record")
    return sorted(data[i:i + 32] for i in range(0, len(data), 32))


def compare(legacy, candidate, workers=(1280, 1281, 256), *, steps=8,
            weights=(0, 50), max_iters=0):
    checks = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        def run(binary, checkpoint, reports, population, weight):
            command = [str(binary), "--packed", "--curve", "131", "--threads", str(population),
                       "--steps", str(steps), "--launches", "2", "--run-id", "11000",
                       "--dp-weight", str(weight), "--verify", "65536" if weight else "0",
                       "--dp-cap", "65536", "--checkpoint", str(checkpoint), "--dp-file", str(reports)]
            if max_iters:
                command += ["--max-iters", str(max_iters)]
            p = subprocess.run(command, capture_output=True, text=True, timeout=300)
            output = p.stdout + p.stderr
            if p.returncode or "MISMATCH" in output or "stopping:" in output:
                raise AssertionError(output)
            match = re.search(r"finished:.*?, (\d+) distinguished points "
                              r"\((\d+) verified against the reference, (\d+) dropped\)", output)
            if not match or int(match[3]) or (weight and (int(match[1]) == 0 or match[1] != match[2])):
                raise AssertionError("incomplete reference verification: " + output)
            header = struct.unpack_from("<8s6IQ", checkpoint.read_bytes())
            if header[:7] != (b"ECC2K130", 2, 131, population, 16, 1, 11000):
                raise AssertionError("unexpected checkpoint shape")
            return {"command": command, "output": output, "verified": int(match[2])}

        for population in workers:
            for weight in weights:
                prefix = root / f"{population}-{weight}"
                a, b = Path(str(prefix) + "-a.ck"), Path(str(prefix) + "-b.ck")
                da, db = a.with_suffix(".bin"), b.with_suffix(".bin")
                runs = [run(legacy, a, da, population, weight),
                        run(candidate, b, db, population, weight)]
                if a.read_bytes() != b.read_bytes() or corpus(da) != corpus(db):
                    raise AssertionError(f"fresh state/corpus differs: workers={population}, DP{weight}")
                # Each binary restores the other one's checkpoint. Compare both
                # with continuing in the legacy binary from its own checkpoint.
                reference = Path(str(prefix) + "-reference.ck")
                shutil.copyfile(a, reference)
                dr = reference.with_suffix(".bin")
                shutil.copyfile(da, dr) if da.exists() else dr.touch()
                runs += [run(legacy, reference, dr, population, weight),
                         run(candidate, a, da, population, weight),
                         run(legacy, b, db, population, weight)]
                state = reference.read_bytes()
                records = corpus(dr)
                if any(path.read_bytes() != state for path in (a, b)):
                    raise AssertionError("cross-binary resume changed checkpoint bytes")
                if any(corpus(path) != records for path in (da, db)):
                    raise AssertionError("cross-binary resume changed DP records")
                checks.append({"workers": population, "dp_weight": weight,
                               "steps": steps, "max_iters": max_iters,
                               "checkpoint_identical": True, "corpus_identical": True,
                               "resume_both_directions": True, "records": len(records),
                               "checkpoint_sha256": hashlib.sha256(state).hexdigest(),
                               "sorted_corpus_sha256": hashlib.sha256(b"".join(records)).hexdigest(),
                               "runs": runs})
                print(json.dumps({k: v for k, v in checks[-1].items() if k != "runs"}), flush=True)
    return {"ok": True, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.legacy.resolve(), args.candidate.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
