"""Isolated, bounded reproduction of the recovered 20B baseline."""
import json
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build/live-22b-baseline"
image = (modal.Image.from_registry(
    "nvidia/cuda:13.3.1-devel-ubuntu24.04", add_python="3.12")
    .entrypoint([]).apt_install("build-essential")
    .add_local_dir(SOURCE, "/opt/ecc22", copy=True,
                   ignore=["build/**", "__pycache__/**", "**/__pycache__/**", "*.pyc", "**/*.pyc"])
    .run_commands("cd /opt/ecc22 && make gpu-rtx-pro6000-20b"))
app = modal.App("ecc2k130-goal22-benchmark")

@app.function(image=image, gpu="RTX-PRO-6000", timeout=900,
              max_containers=1, retries=0)
def reproduce():
    import hashlib
    import subprocess
    import sys
    sys.path.insert(0, "/opt/ecc22")
    from codegen.benchreport import benchResult, reportsVerified, summarizeSamples
    root = Path("/opt/ecc22")
    result = {"targetM": 22000, "phase": "baseline reproduction",
              "manifest": json.loads((root / "snapshot-manifest.json").read_text()),
              "binary_sha256": hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()}
    def run(args, timeout=180):
        p = subprocess.run(args, cwd=root, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        print(p.stdout, flush=True)
        return {"command": args, "returncode": p.returncode, "raw": p.stdout}
    result["compiler"] = run(["nvcc", "--version"])
    result["gpu"] = run(["nvidia-smi", "--query-gpu=name,uuid,driver_version,clocks.sm,power.limit",
                          "--format=csv"])
    base = ["./ecc2k130", "--curve", "131", "--packed"]
    check = run(base + ["--dp-weight", "50", "--steps", "16", "--launches", "6",
                       "--dp-cap", "262144", "--verify", "300"])
    result["replay"] = check
    if not reportsVerified(check["returncode"], check["raw"], required=300):
        result["error"] = "Report replay failed; timings not accepted"
        return result
    args = base + ["--bench", "--steps", "1024", "--launches", "64", "--verify", "0"]
    result["warmup"] = run(args)
    samples = []
    for _ in range(5):
        row = run(args)
        samples.append(benchResult(row["command"], row["returncode"], row["raw"]))
    result["timing"] = summarizeSamples(samples)
    result["collection"] = run(base + ["--dp-weight", "34", "--steps", "1024",
        "--launches", "64", "--verify", "0", "--dp-file", "/tmp/goal22-dp.bin"])
    # This receipt alone never certifies a new walk or changes production.
    return result

sweep_image = image.add_local_file(Path(__file__).with_name("inversion_sweep.py"),
                                  "/opt/inversion_sweep.py").add_local_file(
                                      Path(__file__).with_name("binary_inverse.h"), "/opt/binary_inverse.h")
for header in ("binary_inverse_window.h", "divsteps_inverse.h", "collective_inverse.cuh", "group_inverse.cuh", "test_collective_inverse.cu", "mixed_product.h", "test_mixed_product.cu", "hybrid_group_inverse.cuh", "gen_frobenius_inverse.py", "test_frobenius_inverse.cu", "compact_metadata.cuh", "metadata_checkpoint.inc", "patch_metadata.py", "test_metadata.cu", "gen_pivot_search.py", "test_pivot.cu", "gen_fixed_sigma.py", "patch_bitplanes.py", "test_bitplanes.cu", "paired_inverse.h", "dual_walk.cuh", "test_paired_inverse.cu", "patch_dual.py", "patch_table_layout.py", "patch_noalias.py", "zip_square.h", "patch_zip_square.py", "rotated_group_inverse.cuh", "lean_group_inverse.cuh", "phase_group_inverse.cuh", "compact_group_inverse.cuh", "poly_square.h", "patch_poly_square.py", "square_reduce.h", "gen_square_reduce.py"):
    sweep_image = sweep_image.add_local_file(Path(__file__).with_name(header), "/opt/" + header)

@app.function(image=sweep_image, gpu="RTX-PRO-6000", timeout=900,
              max_containers=1, retries=0)
def inversion_sweep(binary: bool = False, improved: bool = False, collective: bool = False, certify: str = "", group: bool = False, mixed: bool = False, hybrid: bool = False, geometry: bool = False, frobenius: bool = False, metadata: bool = False, scheduling: bool = False, batching: bool = False, bitplanes: bool = False, dual: bool = False, widths: bool = False, table_layout: bool = False, hybrid_geometry: bool = False, fused_batches: bool = False, noalias: bool = False, zip_square: bool = False, rotated_groups: bool = False, finish_tuning: bool = False, lean_groups: bool = False, report_gate: bool = False, phase_groups: bool = False, compact_groups: bool = False, poly_square: bool = False):
    import sys
    sys.path.insert(0, "/opt")
    from inversion_sweep import execute
    return execute("/opt/ecc22", binary=binary or improved, improved=improved, collective=collective or group or hybrid or rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square, certify=certify, group=group or hybrid or rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square, mixed=mixed, hybrid=hybrid, geometry=geometry, frobenius=frobenius, metadata=metadata or batching or bitplanes or dual or widths or hybrid_geometry or fused_batches or noalias or zip_square or rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square, scheduling=scheduling, batching=batching or bitplanes or dual or fused_batches or compact_groups, bitplanes=bitplanes, dual=dual, widths=widths, table_layout=table_layout, hybrid_geometry=hybrid_geometry, fused_batches=fused_batches, noalias=noalias or zip_square or rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square, zip_square=zip_square, rotated_groups=rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square, finish_tuning=finish_tuning or report_gate or phase_groups, lean_groups=lean_groups, report_gate=report_gate, phase_groups=phase_groups, compact_groups=compact_groups, poly_square=poly_square)

@app.local_entrypoint()
def main(sweep: bool = False, binary: bool = False, improved: bool = False, collective: bool = False, certify: str = "", group: bool = False, mixed: bool = False, hybrid: bool = False, geometry: bool = False, frobenius: bool = False, metadata: bool = False, scheduling: bool = False, batching: bool = False, bitplanes: bool = False, dual: bool = False, widths: bool = False, table_layout: bool = False, hybrid_geometry: bool = False, fused_batches: bool = False, noalias: bool = False, zip_square: bool = False, rotated_groups: bool = False, finish_tuning: bool = False, lean_groups: bool = False, report_gate: bool = False, phase_groups: bool = False, compact_groups: bool = False, poly_square: bool = False):
    result = inversion_sweep.remote(binary, improved, collective, certify, group, mixed, hybrid, geometry, frobenius, metadata, scheduling, batching, bitplanes, dual, widths, table_layout, hybrid_geometry, fused_batches, noalias, zip_square, rotated_groups, finish_tuning, lean_groups, report_gate, phase_groups, compact_groups, poly_square) if sweep or binary or improved or collective or group or mixed or hybrid or geometry or frobenius or metadata or scheduling or batching or bitplanes or dual or widths or table_layout or hybrid_geometry or fused_batches or noalias or zip_square or rotated_groups or finish_tuning or lean_groups or report_gate or phase_groups or compact_groups or poly_square else reproduce.remote()
    out = ROOT / "build/goal22-results"
    out.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    path = out / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved receipt: {path}")
    print(json.dumps({"error": result.get("error"),
                      "timing": {k: v for k, v in result.get("timing", {}).items()
                                 if k != "samples"}}, indent=2))
