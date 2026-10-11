"""Run the frozen N41 affine-plane source against public ordinary targets."""

import hashlib
import json
import subprocess
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = HERE.parent / "n131_affine_plane_block_inverse_20261010"
SOURCE = HERE.parent / "n41_coupled_sixpair_full_ic_20261010"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "panel_protocol.json").read_text())
    paths = {"runner": Path(__file__), "public": HERE / "public_targets.json",
             "binary": PRIOR / "plane_worker", "worker_source": PRIOR / "plane_worker.cpp",
             "atoms": SOURCE / "online_atoms.txt", "logs": SOURCE / "online_logs.txt",
             "prior_audit": PRIOR / "plane_sage_audit.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    public = json.loads(paths["public"].read_text())
    assert public["target_count"] == protocol["target_count"] == 16
    assert protocol["online_cap_seconds"] == 120
    assert protocol["max_accepted_probes"] == 20_000_000
    assert protocol["parent_wall_cap_seconds"] == 135
    assert json.loads(paths["prior_audit"].read_text())["status"].startswith("PASS_")

    rows = []
    for record in public["targets"]:
        index, target = record["index"], record["target"]
        assert index == len(rows)
        out_dir = HERE / f"run_{index:02d}"
        out_dir.mkdir(exist_ok=False)
        cmd = [str(paths["binary"]), str(paths["atoms"]), str(paths["logs"]),
               str(out_dir / "hit.json"), str(out_dir / "native.json"),
               str(protocol["max_accepted_probes"]), str(protocol["online_cap_seconds"])]
        start = time.monotonic_ns()
        try:
            completed = subprocess.run(cmd, cwd=ROOT,
                                       input=f"{target[0]} {target[1]}\n", text=True,
                                       capture_output=True,
                                       timeout=protocol["parent_wall_cap_seconds"])
            exit_code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = None
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        outer_wall_ns = time.monotonic_ns() - start
        (out_dir / "stdout.txt").write_text(stdout)
        (out_dir / "stderr.txt").write_text(stderr)
        native_path = out_dir / "native.json"
        native = json.loads(native_path.read_text()) if native_path.exists() else None
        status = native["status"] if native is not None and exit_code == 0 else (
            "PARENT_TIMEOUT" if exit_code is None else "WORKER_FAILURE")
        row = {"index": index, "target": target, "status": status,
               "exit_code": exit_code, "outer_wall_ns": outer_wall_ns,
               "online_ns": native.get("online_ns") if native else None,
               "setup_ns": native.get("setup_ns") if native else None,
               "accepted_probes": native.get("accepted_probes") if native else None,
               "peak_rss_bytes": native.get("peak_rss_bytes") if native else None,
               "source_sha256": {name: digest(out_dir / name) for name in
                                 ("stdout.txt", "stderr.txt")},
               "native_sha256": digest(native_path) if native_path.exists() else None,
               "hit_sha256": digest(out_dir / "hit.json") if (out_dir / "hit.json").exists() else None}
        with (out_dir / "run.json").open("x") as out:
            json.dump(row, out, indent=2, sort_keys=True)
            out.write("\n")
        rows.append(row)
        print(json.dumps({"index": index, "status": status,
                          "online_ns": row["online_ns"],
                          "accepted_probes": row["accepted_probes"]}), flush=True)

    receipt = {"status": "COMPLETE_PANEL", "rows": rows,
               "source_sha256": {name: digest(path) for name, path in paths.items()},
               "protocol_sha256": digest(HERE / "panel_protocol.json")}
    with (HERE / "panel_result.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")


if __name__ == "__main__":
    main()
