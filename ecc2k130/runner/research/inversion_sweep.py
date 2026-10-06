"""Bounded arithmetic-preserving inversion inlining experiment."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import difflib
import re
import shlex
import math

def execute(root, binary=False, improved=False, collective=False, certify="", group=False, mixed=False, hybrid=False, geometry=False, frobenius=False, metadata=False, scheduling=False, batching=False, bitplanes=False, dual=False, widths=False, table_layout=False, hybrid_geometry=False, fused_batches=False, noalias=False, zip_square=False, rotated_groups=False, finish_tuning=False, lean_groups=False, report_gate=False, phase_groups=False, compact_groups=False, poly_square=False):
    root = Path(root)
    sys.path.insert(0, str(root))
    from codegen.benchreport import benchResult, reportsVerified, summarizeSamples
    result = {"hypothesis": "inline inversion arithmetic to expose scheduling",
              "targetM": 22000, "variants": {}, "samples": {}}
    def run(args, timeout=180, quiet=False):
        try:
            p = subprocess.run(args, cwd=root, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            output = error.stdout or ""
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            output += f"\nTimed out after {timeout} seconds\n"
            print(output[-1800:] if quiet else output, flush=True)
            return {"command": args, "returncode": 124, "raw": output, "timeout_seconds": timeout}
        print(p.stdout[-1800:] if quiet else p.stdout, flush=True)
        return {"command": args, "returncode": p.returncode, "raw": p.stdout}
    def sample_result(row):
        sample = benchResult(row["command"], row["returncode"], row["raw"])
        geometry = re.search(r"backend cuda-packed131: (\d+) threads x (\d+) slots x (\d+) lanes = (\d+) walks, dp weight \d+, (\d+) steps per launch", row["raw"])
        counts = re.findall(r"(\d+) iterations\s+\d+ dp", row["raw"])
        launches = int(row["command"][row["command"].index("--launches") + 1])
        expected = int(geometry[4]) * int(geometry[5]) * launches if geometry else 0
        sample["expected_iterations"] = expected
        sample["completed_iterations"] = int(counts[-1]) if counts else 0
        if geometry:
            sample.update(threads=int(geometry[1]), batch=int(geometry[2]), walks=int(geometry[4]))
        if not expected or sample["completed_iterations"] != expected:
            sample.update(valid=False, rate=0, error="missing or incomplete scalar iteration count")
        reports = re.search(r"finished:.*?, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)", row["raw"])
        if not reports or int(reports[3]) != 0:
            sample.update(valid=False, rate=0, error="missing report accounting or dropped reports")
        return sample
    result["compiler"] = run(["nvcc", "--version"])
    result["gpu_before"] = run(["nvidia-smi", "--query-gpu=name,uuid,driver_version,power.limit",
                                 "--format=csv"])
    (root / "goal22-properties.cu").write_text('''#include <cuda_runtime.h>
#include <cstdio>
int main(){cudaDeviceProp p{};auto e=cudaGetDeviceProperties(&p,0);
if(e!=cudaSuccess)return 1;
printf("SMs=%d L2_bytes=%d persisting_L2_bytes=%d shared_per_SM=%zu regs_per_SM=%d max_threads_per_SM=%d\\n",
p.multiProcessorCount,p.l2CacheSize,p.persistingL2CacheMaxSize,p.sharedMemPerMultiprocessor,p.regsPerMultiprocessor,p.maxThreadsPerMultiProcessor);
}
''')
    result["properties_build"] = run(["nvcc", "goal22-properties.cu", "-o", "goal22-properties"], quiet=True)
    if result["properties_build"]["returncode"] == 0:
        result["properties"] = run(["./goal22-properties"])
    result["source_manifest"] = json.loads((root / "snapshot-manifest.json").read_text())
    headers = ["include/packed131.h", "include/packedsigma131.h"]
    if bitplanes:
        headers.append("include/packedcompactstate.cuh")
    if scheduling or table_layout or finish_tuning or (poly_square and geometry):
        headers.append("include/packedtablewalk.cuh")
    if binary or collective or mixed or frobenius or metadata:
        headers.append("include/packedkernels.cuh")
        result["hypothesis"] = "replace serial Itoh-Tsujii inversion with binary polynomial GCD"
    if collective:
        headers.append("include/packedengine.cuh")
        result["hypothesis"] = "share inversions across warps using a zero-safe product tree"
        collective_header = "/opt/hybrid_group_inverse.cuh" if hybrid else ("/opt/group_inverse.cuh" if group else "/opt/collective_inverse.cuh")
        if rotated_groups:
            collective_header = "/opt/rotated_group_inverse.cuh"
        if lean_groups:
            collective_header = "/opt/lean_group_inverse.cuh"
        if phase_groups:
            collective_header = "/opt/phase_group_inverse.cuh"
        if compact_groups:
            collective_header = "/opt/compact_group_inverse.cuh"
        if group:
            result["hypothesis"] += "; independent group barriers"
        shutil.copy2(collective_header, root / "include/collective_inverse.cuh")
        if certify in ("warps4_inline640", "warps4_inline512"):
            selected = root / "include/collective_inverse.cuh"
            source = selected.read_text()
            old = "__device__ __noinline__ P131 goal22CollectiveInverse"
            assert source.count(old) == 1
            selected.write_text(source.replace(old, "__device__ __forceinline__ P131 goal22CollectiveInverse"))
        if hybrid:
            for header in ("binary_inverse_window.h", "divsteps_inverse.h"):
                shutil.copy2("/opt/" + header, root / "include" / header)
            result["root_sources"] = {header: Path("/opt/" + header).read_text()
                for header in ("binary_inverse_window.h", "divsteps_inverse.h")}
        result["probes"] = []
        for mode in ((1, 2) if hybrid else (0,)):
            probe_flags = ["-DGOAL22_GROUP_BARRIER_TEST=1"] if group else []
            if phase_groups:
                probe_flags.append("-DGOAL22_EXPECT_PHASE=1")
            probe_flags += ["-DGOAL22_ROOT_MODE=" + str(mode)]
            probe = run(["nvcc", *probe_flags, "-O3", "-std=c++17", "-arch=sm_120", "-DECC_THREADS=512",
                "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
                "-DECC_PACKED_PERM_SIGMA=3", "-DECC_PACKED_UNROLL_INV=1", "-Iinclude",
                "/opt/test_collective_inverse.cu", "-o", "test-collective-inverse"], quiet=True)
            record = {"root_mode": mode, "build": probe}
            record["selected_header_sha256"] = hashlib.sha256((root / "include/collective_inverse.cuh").read_bytes()).hexdigest()
            result["probes"].append(record)
            if probe["returncode"]:
                result["error"] = "collective inverse probe failed to compile"
                return result
            record["check"] = run(["./test-collective-inverse"])
            if record["check"]["returncode"]:
                result["error"] = "collective inverse independent device checks failed"
                return result
        if phase_groups:
            # Repair the earlier probe's quoted-include selection gap for the
            # previous leader and lean variant, retaining distinct evidence.
            result["revalidated_helpers"] = []
            try:
                for helper in ("rotated_group_inverse.cuh", "lean_group_inverse.cuh"):
                    shutil.copy2("/opt/" + helper, root / "include/collective_inverse.cuh")
                    record = {"helper": helper, "selected_header_sha256": hashlib.sha256(
                        (root / "include/collective_inverse.cuh").read_bytes()).hexdigest()}
                    record["build"] = run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                        "-DGOAL22_GROUP_BARRIER_TEST=1", "-DECC_THREADS=512", "-DECC_PACKED_SINGLE_PRODUCT=1",
                        "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1", "-DECC_PACKED_PERM_SIGMA=3",
                        "-DECC_PACKED_UNROLL_INV=1", "-Iinclude", "/opt/test_collective_inverse.cu",
                        "-o", "test-selected-helper"], quiet=True)
                    result["revalidated_helpers"].append(record)
                    if record["build"]["returncode"]:
                        result["error"] = "selected helper revalidation build failed: " + helper
                        return result
                    record["check"] = run(["./test-selected-helper"])
                    if record["check"]["returncode"]:
                        result["error"] = "selected helper revalidation failed: " + helper
                        return result
            finally:
                shutil.copy2(collective_header, root / "include/collective_inverse.cuh")
        if lean_groups:
            sanitizer = shutil.which("compute-sanitizer")
            result["sanitizers"] = {"available": bool(sanitizer), "checks": []}
            if sanitizer:
                # Establish instrumentation capability on an unrelated kernel.
                # Unsupported infrastructure is recorded, never called a pass.
                state = result["sanitizers"]
                state["version"] = run([sanitizer, "--version"], quiet=True)
                (root / "sanitizer-control.cu").write_text('''#include <cuda_runtime.h>
#include <cstdio>
__global__ void write_control(int *p) { p[threadIdx.x] = int(threadIdx.x); }
int main() {
    int *p, h[32];
    if (cudaMalloc(&p, sizeof(h)) != cudaSuccess) return 2;
    write_control<<<1,32>>>(p);
    if (cudaDeviceSynchronize() != cudaSuccess) return 3;
    if (cudaMemcpy(h,p,sizeof(h),cudaMemcpyDeviceToHost) != cudaSuccess) return 4;
    for (int i=0;i<32;++i) if (h[i]!=i) return 5;
    if (cudaFree(p) != cudaSuccess) return 6;
    puts("PASS sanitizer control");
}
''')
                state["control_build"] = run(["nvcc", "-arch=sm_120", "sanitizer-control.cu",
                                               "-o", "sanitizer-control"], quiet=True)
                if state["control_build"]["returncode"]:
                    result["error"] = "sanitizer capability control failed to compile"
                    return result
                state["control"] = run([sanitizer, "--tool", "memcheck", "--error-exitcode", "99",
                                         "./sanitizer-control"], timeout=90, quiet=True)
                control = state["control"]
                unsupported = (control["returncode"] == 99
                    and 'Error: Device not supported.' in control["raw"]
                    and 'PASS sanitizer control' in control["raw"]
                    and 'ERROR SUMMARY: 1 error' in control["raw"]
                    and control["raw"].count('========= Error:') == 1)
                state["status"] = "unavailable_device_unsupported" if unsupported else "pending"
                if control["returncode"] and not unsupported:
                    result["error"] = "sanitizer capability control failed"
                    return result
                for tool in (() if unsupported else ("memcheck", "racecheck", "synccheck")):
                    check = run([sanitizer, "--tool", tool, "--error-exitcode", "99",
                                 "./test-collective-inverse"], timeout=90, quiet=True)
                    result["sanitizers"]["checks"].append({"tool": tool, **check})
                    if check["returncode"]:
                        result["error"] = "lean-group sanitizer check did not pass: " + tool
                        return result
                if not unsupported:
                    state["status"] = "passed"
    if mixed:
        result["hypothesis"] = "offload selected 64-bit leaves from CLMAD to integer arithmetic"
        shutil.copy2("/opt/mixed_product.h", root / "include/mixed_product.h")
        result["probe_build"] = run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
            "-DECC_PACKED_CLMAD=1", "-Iinclude", "/opt/test_mixed_product.cu",
            "-o", "test-mixed-product"], quiet=True)
        if result["probe_build"]["returncode"]:
            result["error"] = "mixed-product probe compilation failed"
            return result
        result["probe"] = run(["./test-mixed-product"])
        if result["probe"]["returncode"]:
            result["error"] = "mixed-product independent device checks failed"
            return result
    if metadata:
        headers += ["include/packedengine.cuh", "src/main.cu"]
        for helper in ("compact_metadata.cuh", "metadata_checkpoint.inc"):
            shutil.copy2("/opt/" + helper, root / "include" / helper)
        result["metadata_sources"] = {h: Path("/opt/" + h).read_text()
            for h in ("compact_metadata.cuh", "metadata_checkpoint.inc", "patch_metadata.py")}
        result["probe_build"] = run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
            "-Iinclude", "/opt/test_metadata.cu", "-o", "test-metadata"], quiet=True)
        if result["probe_build"]["returncode"]:
            result["error"] = "metadata probe compilation failed"
            return result
        result["probe"] = run(["./test-metadata"])
        if result["probe"]["returncode"]:
            result["error"] = "metadata independent device checks failed"
            return result
        if report_gate:
            record = {"build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DGOAL22_FULL_HIST=1", "-Iinclude", "/opt/test_metadata.cu", "-o", "test-full-history"], quiet=True)}
            result["full_hist_probe"] = record
            if record["build"]["returncode"]:
                result["error"] = "full history probe compilation failed"
                return result
            record["check"] = run(["./test-full-history"])
            if record["check"]["returncode"]:
                result["error"] = "full history reference comparison failed"
                return result
    if dual:
        from gen_fixed_sigma import generate
        (root / "include/fixed_sigma.h").write_text(generate(True))
        for helper in ("paired_inverse.h", "dual_walk.cuh"):
            shutil.copy2("/opt/" + helper, root / "include" / helper)
        result["dual_sources"] = {h: (root / "include" / h).read_text()
            for h in ("fixed_sigma.h", "paired_inverse.h", "dual_walk.cuh")}
        record = {"build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
            "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
            "-Iinclude", "/opt/test_paired_inverse.cu", "-o", "test-paired-inverse"], quiet=True)}
        result["dual_probe"] = record
        if record["build"]["returncode"]:
            result["error"] = "paired inverse probe failed to compile"
            return result
        record["check"] = run(["./test-paired-inverse"])
        if record["check"]["returncode"]:
            result["error"] = "paired inverse independent device comparison failed"
            return result
    headers = list(dict.fromkeys(headers))
    original = {name: (root / name).read_text() for name in headers}
    shutil.copy2(root / "ecc2k130", root / "baseline")
    binaries = {"baseline": "./baseline"}
    arms = [("inline_mul", True, False),
                              ("inline_sigma", False, True),
                              ("inline_both", True, True)]
    if binary:
        arms = [("binary_inline", False, False), ("binary_noinline", False, False)]
    if improved:
        arms = [("window_inline", False, False), ("divsteps_inline", False, False),
                ("divsteps_noinline", False, False)]
    if collective:
        arms = [("warps" + str(w), False, False) for w in ((2, 4, 8) if group else (2, 4, 8, 16))]
    if hybrid:
        arms = [(n, False, False) for n in ("warps4_window", "warps8_window", "warps8_divsteps")]
    if mixed:
        arms = [(n,False,False) for n in ("mixed_single", "mixed_single_inverse", "mixed_pairs")]
    geometry_options = {
        "threads640": {"THREADS": "640"},
        "threads640_no_pipeline": {"THREADS": "640", "TABLE_PIPE_SELECT": "0"},
        "threads640_low_live": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
        "threads768_low_live": {"THREADS": "768", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
    }
    if geometry:
        result["hypothesis"] = "increase active warps with lower register liveness in the fully inlined kernel"
        arms = [(n, False, False) for n in geometry_options]
    if frobenius:
        result["hypothesis"] = "keep inversion in the polynomial basis with cached Frobenius lookup maps"
        arms = [("frobenius_nibble", False, False), ("frobenius_byte", False, False)]
    if metadata:
        result["hypothesis"] = "compact live metadata to keep wider launch geometry within L2"
        geometry_options = {
            "metadata512": {},
            "metadata640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
            "metadata768": {"THREADS": "768", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
        }
        arms = [(n, False, False) for n in geometry_options]
    if scheduling:
        result["hypothesis"] = "reduce selection lookups and specialize fixed inversion permutations"
        arms = [(n, False, False) for n in ("pivot_scan", "pivot_group4", "fixed_sigma", "fixed_sigma_inline")]
    if batching:
        assert metadata
        result["hypothesis"] = "amortize inversion over larger batches with compact live metadata"
        geometry_options = {
            "batch24_threads512": {"BATCH": "24", "THREADS": "512"},
            "batch28_threads416": {"BATCH": "28", "THREADS": "416"},
            "batch32_threads384": {"BATCH": "32", "THREADS": "384"},
        }
        arms = [(n, False, False) for n in geometry_options]
    if bitplanes:
        assert batching and metadata
        result["hypothesis"] = "pack field tails cooperatively to fit larger batches in L2"
        geometry_options = {
            "bitplanes_batch24_threads512": {"BATCH": "24", "THREADS": "512"},
            "bitplanes_batch32_threads384": {"BATCH": "32", "THREADS": "384"},
        }
        arms = [(n, False, False) for n in geometry_options]
    if dual:
        assert batching and metadata
        result["hypothesis"] = "interleave two independent 16-point chains per CUDA thread at fixed arithmetic per update"
        geometry_options = {
            "dual_threads256": {"BATCH": "32", "THREADS": "256"},
            "dual_threads320": {"BATCH": "32", "THREADS": "320"},
        }
        arms = [(n, False, False) for n in geometry_options]
    if widths:
        assert metadata and not batching
        result["hypothesis"] = "refine occupancy near the only repeatable improvement with independent byte flags"
        geometry_options = {
            f"byte_metadata{n}": {"THREADS": str(n), "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in (640, 704, 736)
        }
        arms = [(n, False, False) for n in geometry_options]
    if table_layout:
        result["hypothesis"] = "transpose read-only shared tables to distribute irregular loads over all banks"
        arms = [(n, False, False) for n in ("table_rows", "table_addends", "table_both")]
        result["table_layout_source"] = Path("/opt/patch_table_layout.py").read_text()
    if hybrid_geometry:
        assert metadata and not table_layout
        result["hypothesis"] = "use a smaller shared selection table to retain L1 while increasing resident blocks"
        geometry_options = {
            "hybrid320x2": {"THREADS": "320", "MINBLOCKS": "2"},
            "hybrid384x2": {"THREADS": "384", "MINBLOCKS": "2"},
            "hybrid256x3": {"THREADS": "256", "MINBLOCKS": "3"},
            "hybrid320x2_alu": {"THREADS": "320", "MINBLOCKS": "2", "PACKED_ALU_SQR": "1"},
        }
        for options in geometry_options.values():
            options.update(TABLE_ADDEND_GLOBAL="1", TABLE_PIPE_SELECT="0", PACKED_PAIR_ILP="0")
        arms = [(n, False, False) for n in geometry_options]
    if fused_batches:
        assert metadata and batching and not table_layout
        result["hypothesis"] = "combine compact metadata with fused passes to reduce memory traffic at larger batches"
        geometry_options = {
            "fused20x576": {"BATCH": "20", "THREADS": "576"},
            "fused24x512": {"BATCH": "24", "THREADS": "512"},
            "fused32x384": {"BATCH": "32", "THREADS": "384"},
        }
        for options in geometry_options.values():
            options.update(TABLE_FUSED="1", TABLE_FUSED_PIPE="1", TABLE_PIPE_SELECT="0", PACKED_PAIR_ILP="0")
        arms = [(n, False, False) for n in geometry_options]
    if noalias:
        assert metadata and (not batching or rotated_groups) and not table_layout
        result["hypothesis"] = "expose disjoint walk buffers as restricted kernel arguments to improve load scheduling"
        geometry_options = {
            "noalias512": {},
            "noalias640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
            "noalias640_alu": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0", "PACKED_ALU_SQR": "1"},
        }
        arms = [(n, False, False) for n in geometry_options]
        result["noalias_source"] = Path("/opt/patch_noalias.py").read_text()
    if zip_square:
        assert metadata and noalias
        result["hypothesis"] = "zip even and odd bit streams to replace normal-basis squaring CLMADs with fewer ALU instructions"
        geometry_options = {
            "noalias640_control": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
            "zip512": {},
            "zip640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
        }
        arms = [(n, False, False) for n in geometry_options]
        shutil.copy2("/opt/zip_square.h", root / "include/zip_square.h")
        result["zip_square_sources"] = {h: Path("/opt/" + h).read_text()
            for h in ("zip_square.h", "patch_zip_square.py")}
    if rotated_groups:
        assert collective and group and metadata and noalias and not zip_square
        result["hypothesis"] = "rotate inversion-tree roots among physical warps while retaining independent group barriers"
        geometry_options = {
            "warps4_rotate512": {},
            "warps4_rotate640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
            "warps8_rotate512": {},
            "warps2_rotate640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
        }
        if batching:
            geometry_options = {
                "warps4_rotate_batch" + str(batch): {"THREADS": "640", "BATCH": str(batch),
                    "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
                for batch in (17, 18)}
            if geometry:
                geometry_options = {
                    f"warps4_rotate_b{batch}_t{threads}": {"THREADS": str(threads), "BATCH": str(batch),
                        "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
                    for batch, threads in ((12, 768), (14, 768), (12, 896))}
                result["hypothesis"] = "more active warps with smaller per-thread batches at comparable L2 footprint"
        elif geometry:
            geometry_options = {
                "warps4_ilp640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "1"},
                "warps4_pipeline640": {"THREADS": "640", "TABLE_PIPE_SELECT": "1", "PACKED_PAIR_ILP": "0"},
                "warps4_ilp_pipeline640": {"THREADS": "640", "TABLE_PIPE_SELECT": "1", "PACKED_PAIR_ILP": "1"},
                "warps4_inline640": {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"},
                "warps4_inline512": {},
            }
            result["hypothesis"] = "revisit instruction overlap after grouped inversion changed register liveness"
        arms = [(n, False, False) for n in geometry_options]
    if finish_tuning:
        assert rotated_groups
        result["hypothesis"] = "combine rotated four-warp inversions with zip squaring and/or transposed sign rows"
        geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in ("warps4_zip640", "warps4_rows640", "warps4_zip_rows640")}
        arms = [(n, False, False) for n in geometry_options]
        shutil.copy2("/opt/zip_square.h", root / "include/zip_square.h")
        result["zip_square_sources"] = {h: Path("/opt/" + h).read_text()
            for h in ("zip_square.h", "patch_zip_square.py")}
        result["table_layout_source"] = Path("/opt/patch_table_layout.py").read_text()
    if lean_groups:
        assert rotated_groups and not finish_tuning and not zip_square
        result["hypothesis"] = "retain right-branch inverses in registers and remove redundant group barriers"
        geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in ("warps4_lean640", "warps4_lean_zip640", "warps2_lean640")}
        if batching:
            geometry_options = {
                n: {"THREADS": "640", "BATCH": str(batch), "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
                for n, batch in (("warps4_lean_batch17", 17), ("warps4_lean_batch18", 18),
                                 ("warps4_lean_zip_batch18", 18))}
            result["hypothesis"] += "; amortize over 17/18 slots while retaining L2 headroom"
        arms = [(n, False, False) for n in geometry_options]
        shutil.copy2("/opt/zip_square.h", root / "include/zip_square.h")
        result["zip_square_sources"] = {h: Path("/opt/" + h).read_text()
            for h in ("zip_square.h", "patch_zip_square.py")}
    if report_gate:
        assert finish_tuning and not lean_groups and not batching
        result["hypothesis"] = "read dead flags only for a report or overdue guard; measure normal L2 caching separately"
        geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in ("warps4_gated640", "warps4_gated_zip_rows640", "warps4_gated_normalcache640", "warps4_gated_hist64")}
        geometry_options["warps4_gated_normalcache640"]["PACKED_L2_PERSIST"] = "0"
        arms = [(n, False, False) for n in geometry_options]
    if phase_groups:
        assert finish_tuning and not lean_groups and not batching and not report_gate
        result["hypothesis"] = "rotate inverse-tree roots across calls to average scheduler work over time"
        geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in ("warps4_phase640", "warps4_phase_zip_rows640", "warps4_phase_period16")}
        arms = [(n, False, False) for n in geometry_options]
    if compact_groups:
        assert rotated_groups and batching and not phase_groups and not finish_tuning and not lean_groups
        result["hypothesis"] = "vectorize grouped inversion scratch and reduce shared storage from 20 to 17 bytes per thread"
        geometry_options = {
            f"warps4_compact_b{batch}_t{threads}": {"THREADS": str(threads), "BATCH": str(batch),
                "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for batch, threads in ((16, 640), (12, 896), (10, 1024))}
        arms = [(n, False, False) for n in geometry_options]
    if poly_square:
        assert rotated_groups and not batching and not finish_tuning and not lean_groups
        result["hypothesis"] = "shorter per-update polynomial bit spread; rebalance one or two limbs onto CLMAD"
        geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
            for n in ("warps4_poly_alu640", "warps4_poly_native1", "warps4_poly_native2")}
        arms = [(n, False, False) for n in geometry_options]
        shutil.copy2("/opt/poly_square.h", root / "include/poly_square.h")
        result["poly_square_sources"] = {h: Path("/opt/" + h).read_text()
            for h in ("poly_square.h", "patch_poly_square.py")}
        if geometry:
            result["hypothesis"] = "reduce each square in packed even/odd coefficient streams before final interleaving"
            geometry_options = {n: {"THREADS": "640", "TABLE_PIPE_SELECT": "0", "PACKED_PAIR_ILP": "0"}
                for n in ("warps4_poly_compact640", "warps4_poly_compact_zip_rows640")}
            arms = [(n, False, False) for n in geometry_options]
            for h in ("square_reduce.h", "zip_square.h"):
                shutil.copy2("/opt/" + h, root / "include" / h)
            result["poly_square_sources"].update({h: Path("/opt/" + h).read_text()
                for h in ("square_reduce.h", "gen_square_reduce.py", "zip_square.h")})
            result["table_layout_source"] = Path("/opt/patch_table_layout.py").read_text()
    if certify:
        arms = [arm for arm in arms if arm[0] == certify]
        if not arms:
            raise ValueError("Unknown certification candidate: " + certify)
        result["certification_candidate"] = certify
    for name, mul, sigma in arms:
        content = dict(original)
        use_zip = (zip_square and name != "noalias640_control") or ((finish_tuning or lean_groups or poly_square) and "zip" in name)
        if report_gate:
            path = "include/packedkernels.cuh"
            old = "if (!p.dead[id]) {"
            assert content[path].count(old) == 3
            content[path] = content[path].replace(old,
                "if ((hw <= p.dpWeight || guard) && !p.dead[id]) {")
        if metadata:
            from patch_metadata import patch
            content = patch(content)
            if report_gate and name.endswith("hist64"):
                content["include/packedkernels.cuh"] = '#define GOAL22_FULL_HIST 1\n' + content["include/packedkernels.cuh"]
        if noalias:
            from patch_noalias import patch
            content = patch(content)
        if use_zip:
            from patch_zip_square import patch
            content["include/packed131.h"] = patch(content["include/packed131.h"])
        if poly_square:
            if geometry:
                from gen_square_reduce import patch
                content["include/packed131.h"] = patch(content["include/packed131.h"])
            else:
                from patch_poly_square import patch
                native = int(name[-1]) if "native" in name else 0
                content["include/packed131.h"] = patch(content["include/packed131.h"], native=native)
        if (finish_tuning or poly_square) and "rows" in name:
            from patch_table_layout import patch
            content["include/packedtablewalk.cuh"] = patch(content["include/packedtablewalk.cuh"], rows=True)
        if bitplanes:
            from patch_bitplanes import patch
            content = patch(content)
        if dual:
            from patch_dual import patch
            content = patch(content)
        if table_layout:
            from patch_table_layout import patch
            path = "include/packedtablewalk.cuh"
            content[path] = patch(content[path], addends=name != "table_rows", rows=name != "table_addends")
        if mul:
            old = "static ECC_BIG P131 mul131(MulArg a, MulArg b)"
            assert content[headers[0]].count(old) == 1
            content[headers[0]] = content[headers[0]].replace(old, old.replace("ECC_BIG", "ECC_HD"))
        if sigma:
            old = "static ECC_BIG P131 sigmaInvNetwork131(P131 a, int index)"
            assert content[headers[1]].count(old) == 1
            content[headers[1]] = content[headers[1]].replace(old, old.replace("ECC_BIG", "ECC_HD"))
        extra = ""
        if scheduling:
            if name.startswith("pivot"):
                from gen_pivot_search import generate, patch
                extra = generate(1 if name == "pivot_scan" else 4)
                (root / "include/pivot_search.cuh").write_text(extra)
                path = "include/packedtablewalk.cuh"
                content[path] = patch(content[path])
            else:
                from gen_fixed_sigma import generate, patch, PROBE_HEADER
                extra = generate(name.endswith("inline"))
                (root / "include/fixed_sigma.h").write_text(extra)
                (root / "include/frobenius_inverse.h").write_text(PROBE_HEADER)
                content["include/packed131.h"] = patch(content["include/packed131.h"])
        if frobenius:
            from gen_frobenius_inverse import generate
            extra = generate(4 if name.endswith("nibble") else 8)
            (root / "include/frobenius_inverse.h").write_text(extra)
            path = "include/packedkernels.cuh"
            content[path] = content[path].replace('#include "packed131.h"',
                '#include "packed131.h"\n#include "frobenius_inverse.h"')
            old = "toPolynomial131(inv131(fromPolynomial131(prod)))"
            assert content[path].count(old) == 2
            content[path] = content[path].replace(old, "goal22FrobeniusInverse(prod)")
            probe_build = run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_INLINE_POLY=3",
                "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
                "-DECC_PACKED_ALU_SQUARE=1", "-Iinclude", "/opt/test_frobenius_inverse.cu",
                "-o", "test-frobenius-inverse"], quiet=True)
            record = {"name": name, "build": probe_build}
            result.setdefault("probes", []).append(record)
            if probe_build["returncode"]:
                result["error"] = "Frobenius inverse probe compilation failed"
                return result
            record["check"] = run(["./test-frobenius-inverse"])
            if record["check"]["returncode"]:
                result["error"] = "Frobenius inverse independent device comparison failed"
                return result
        if binary:
            extra = Path("/opt/binary_inverse.h").read_text()
            if name.startswith("window"):
                extra = Path("/opt/binary_inverse_window.h").read_text().replace("goal22WindowInverse", "goal22BinaryInverse")
            if name.startswith("divsteps"):
                extra = Path("/opt/divsteps_inverse.h").read_text().replace("goal22DivstepsInverse", "goal22BinaryInverse")
            if name.endswith("noinline"):
                extra = extra.replace("ECC_HD P131 goal22BinaryInverse", "static ECC_BIG P131 goal22BinaryInverse")
            (root / "include/binary_inverse.h").write_text(extra)
            path = "include/packedkernels.cuh"
            content[path] = content[path].replace('#include "packed131.h"',
                '#include "packed131.h"\n#include "binary_inverse.h"')
            old = "toPolynomial131(inv131(fromPolynomial131(prod)))"
            assert content[path].count(old) == 2
            content[path] = content[path].replace(old, "goal22BinaryInverse(prod)")
        if collective:
            warps = int(name.removeprefix("warps").split("_")[0])
            extra = Path(collective_header).read_text()
            if hybrid:
                mode = 1 if name.endswith("window") else 2
                extra = "#define GOAL22_ROOT_MODE " + str(mode) + "\n" + extra
            if name in ("warps4_inline640", "warps4_inline512"):
                old = "__device__ __noinline__ P131 goal22CollectiveInverse"
                assert extra.count(old) == 1
                extra = extra.replace(old, "__device__ __forceinline__ P131 goal22CollectiveInverse")
            (root / "include/collective_inverse.cuh").write_text(extra)
            path = "include/packedkernels.cuh"
            content[path] = content[path].replace('#include "packed131.h"',
                '#include "packed131.h"\n#include "collective_inverse.cuh"')
            old = "toPolynomial131(inv131(fromPolynomial131(prod)))"
            assert content[path].count(old) == 2
            phase = (", unsigned(step >> 4)" if "period16" in name else ", unsigned(step)") if phase_groups else ""
            content[path] = content[path].replace(old,
                f"(((blockIdx.x + 1) * blockDim.x <= p.threads) ? goal22CollectiveInverse<{warps}>(prod{phase}) : {old})")
            path = "include/packedengine.cuh"
            old = "if (dynamicSharedBytes() > 48 * 1024)"
            assert content[path].count(old) == 1
            content[path] = content[path].replace(old, "if (dynamicSharedBytes() > 0)")
        if mixed:
            extra = Path("/opt/mixed_product.h").read_text().replace("namespace eccPacked131 {\n", "").replace("} // namespace eccPacked131\n", "")
            (root / "include/mixed_product_body.h").write_text(extra)
            path = "include/packed131.h"
            marker = "#if ECC_PACKED_PAIR_CLMUL\n/* Two independent"
            assert content[path].count(marker) == 1
            content[path] = content[path].replace(marker, '#include "mixed_product_body.h"\n' + marker)
            if name in ("mixed_single", "mixed_single_inverse"):
                old = "uint32_t h[9]; product131(a,b,h);"
                assert content[path].count(old) == 1
                content[path] = content[path].replace(old, "uint32_t h[9]; goal22ProductMixed(a,b,h);")
            if name == "mixed_single_inverse":
                old = "product131(pa,pb,h);"
                assert content[path].count(old) == 1
                content[path] = content[path].replace(old, "goal22ProductMixed(pa,pb,h);")
            if name == "mixed_pairs":
                old = "product131(a,c,hc);"
                assert content[path].count(old) == 1
                content[path] = content[path].replace(old, "goal22ProductMixed(a,c,hc);")
                path = "include/packedkernels.cuh"
                old = "product131(prod, ep, hb);"
                assert content[path].count(old) == 1
                content[path] = content[path].replace(old, "goal22ProductMixed(prod, ep, hb);")
        diff = ""
        for path in headers:
            (root / path).write_text(content[path])
            diff += "".join(difflib.unified_diff(original[path].splitlines(True),
                content[path].splitlines(True), fromfile="a/"+path, tofile="b/"+path))
        if use_zip or poly_square:
            from gen_fixed_sigma import PROBE_HEADER
            (root / "include/frobenius_inverse.h").write_text(PROBE_HEADER)
            record = {"name": name, "build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
                "-DECC_PACKED_PERM_SIGMA=3", "-DECC_PACKED_UNROLL_INV=1", "-DECC_PACKED_FROM_REDUCED=1",
                "-Iinclude", "/opt/test_frobenius_inverse.cu", "-o", "test-zip-square"], quiet=True)}
            result.setdefault("probes", []).append(record)
            if record["build"]["returncode"]:
                result["error"] = "field arithmetic device probe compilation failed"
                return result
            record["check"] = run(["./test-zip-square"])
            if record["check"]["returncode"]:
                result["error"] = "field arithmetic probes differ from independent reference"
                return result
            if collective:
                record = {"name": name, "build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                    *(["-DGOAL22_EXPECT_PHASE=1"] if phase_groups else []),
                    "-DGOAL22_GROUP_BARRIER_TEST=1", "-DECC_THREADS=512", "-DECC_PACKED_SINGLE_PRODUCT=1",
                    "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1", "-DECC_PACKED_PERM_SIGMA=3",
                    "-DECC_PACKED_UNROLL_INV=1", "-DECC_PACKED_FROM_REDUCED=1", "-Iinclude",
                    "/opt/test_collective_inverse.cu", "-o", "test-zip-collective"], quiet=True)}
                result.setdefault("zip_collective_probes", []).append(record)
                if record["build"]["returncode"]:
                    result["error"] = "combined zip/group probe compilation failed"
                    return result
                record["check"] = run(["./test-zip-collective"])
                if record["check"]["returncode"]:
                    result["error"] = "combined zip/group inverses differ from reference"
                    return result
        if bitplanes and "bitplane_probe" not in result:
            record = {"build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DECC_BATCH=3", "-DECC_PACKED_COMPACT_STATE=1", "-DECC_TABLE_TAG_DENOM=1",
                "-Iinclude", "/opt/test_bitplanes.cu", "-o", "test-bitplanes"], quiet=True)}
            result["bitplane_probe"] = record
            if record["build"]["returncode"]:
                result["error"] = "bitplane codec probe compilation failed"
                return result
            record["check"] = run(["./test-bitplanes"])
            if record["check"]["returncode"]:
                result["error"] = "bitplane codec independent device checks failed"
                return result
        if table_layout:
            record = {"name": name, "build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DECC_WALK_TABLE=1", "-DECC_TABLE_PIVOT_BYTES=1", "-DECC_PACKED_SINGLE_PRODUCT=1",
                "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1", "-DECC_PACKED_FROM_REDUCED=1",
                "src/testtablewalkcuda.cu", "-o", "test-table-layout"], quiet=True)}
            result.setdefault("probes", []).append(record)
            if record["build"]["returncode"]:
                result["error"] = "table layout device probe compilation failed"
                return result
            record["check"] = run(["./test-table-layout"])
            if record["check"]["returncode"]:
                result["error"] = "table layout differs from independent reference"
                return result
        if scheduling:
            probe_source = "/opt/test_pivot.cu" if name.startswith("pivot") else "/opt/test_frobenius_inverse.cu"
            record = {"name": name, "build": run(["nvcc", "-O3", "-std=c++17", "-arch=sm_120",
                "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_CLMAD=1", "-DECC_PACKED_DIRECT_REDUCE=1",
                "-DECC_PACKED_PERM_SIGMA=3", "-DECC_PACKED_UNROLL_INV=1", "-Iinclude",
                probe_source, "-o", "test-scheduling"], quiet=True)}
            result.setdefault("probes", []).append(record)
            if record["build"]["returncode"]:
                result["error"] = "scheduling primitive probe failed to compile"
                return result
            record["check"] = run(["./test-scheduling"])
            if record["check"]["returncode"]:
                result["error"] = "scheduling primitive independent comparison failed"
                return result
        build_args = ["make", "gpu-rtx-pro6000-20b"]
        if geometry or metadata:
            recipe = (root / "Makefile").read_text().split("gpu-rtx-pro6000-20b:\n", 1)[1].split("\n\n", 1)[0]
            build_args = shlex.split(recipe.replace("\\\n", " ").replace("$(MAKE)", "make"))
            options = geometry_options[name]
            # Existing knobs omitted by the preset may be added explicitly.
            assert all(re.search(r"^" + re.escape(k) + r"\s*\?=", (root / "Makefile").read_text(), re.M) for k in options)
            missing = {k: v for k, v in options.items() if not any(a.startswith(k + "=") for a in build_args)}
            build_args = [a.split("=", 1)[0] + "=" + options[a.split("=", 1)[0]]
                          if a.split("=", 1)[0] in options else a for a in build_args]
            build_args += [k + "=" + v for k, v in missing.items()]
        row = {"patch": diff, "extra_header": extra,
               "build": run(build_args, quiet=True)}
        result["variants"][name] = row
        if row["build"]["returncode"]:
            continue
        shutil.copy2(root / "ecc2k130", root / name)
        binaries[name] = "./" + name
    for path in headers:
        (root / path).write_text(original[path])
    accepted = {}
    batches = {name: int(geometry_options.get(name, {}).get("BATCH", 16)) if batching else 16
               for name in binaries}
    # Identical scalar populations with whole CUDA warps for every batch.
    # Preserve the old population where possible, otherwise round upward.
    replay_multiple = 32 * math.lcm(*batches.values())
    replay_minimum = 107520 if batching else 65536
    replay_walks = ((replay_minimum + replay_multiple - 1) // replay_multiple) * replay_multiple
    result["replay_walks"] = replay_walks
    replay_steps = 64 if phase_groups else 16
    result["replay_steps"] = replay_steps
    guard_reference = None
    for name, binary in binaries.items():
        row = result["variants"].setdefault(name, {})
        row["binary_sha256"] = hashlib.sha256((root / binary).read_bytes()).hexdigest()
        args = [binary, "--curve", "131", "--packed"]
        corpus = root / (name + "-replay.bin")
        replay_extra = ["--threads", str(replay_walks // batches[name]), "--dp-file", str(corpus)]
        row["replay"] = run(args + ["--dp-weight", "50", "--steps", str(replay_steps),
            "--launches", "6", "--dp-cap", "262144", "--verify", "300"] + replay_extra)
        check = row["replay"]
        row["reports_ok"] = reportsVerified(check["returncode"], check["raw"], required=300)
        if row["reports_ok"]:
            data = corpus.read_bytes()
            if len(data) % 32:
                raise ValueError("partial DP record")
            # Compare the complete multiset, including duplicates. GPU report
            # order is nondeterministic; the record's seed and canonical x are not.
            digest = hashlib.sha256(b"".join(sorted(data[i:i+32] for i in range(0, len(data), 32)))).hexdigest()
            row["corpus"] = {"records": len(data) // 32, "sorted_sha256": digest}
            if name != "baseline" and row["corpus"] != result["variants"]["baseline"].get("corpus"):
                row["reports_ok"] = False
                row["error"] = "full DP multiset differs from baseline"
        if row["reports_ok"]:
            if report_gate:
                # Exercise rare overdue/reseed branches, then compare the entire
                # logical checkpoint including flags, seeds and live history.
                import struct
                checkpoint = root / (name + "-guard.ckpt")
                checkpoint.unlink(missing_ok=True)
                check = run(args + ["--threads", "1280", "--dp-weight", "0",
                    "--max-iters", "4096", "--steps", "4096", "--launches", "3",
                    "--verify", "0", "--checkpoint", str(checkpoint)])
                state = bytearray(checkpoint.read_bytes()) if checkpoint.exists() else bytearray()
                walks = 1280 * 16
                valid = check["returncode"] == 0 and len(state) == 40 + 68 * walks
                reseeded = 0
                if valid:
                    magic, version, curve, threads, batch, lanes, run_id, iteration = struct.unpack_from('<8s6IQ', state)
                    valid = (magic == b'ECC2K130' and version == 3 and curve == 131
                             and threads == 1280 and batch == 16 and lanes == 1 and iteration == 12288)
                    reseeded = sum(struct.unpack_from('<Q', state, 40 + 52 * walks + 8 * i)[0] > 0
                                   for i in range(walks))
                    # Only bits 48..63 of the four-tag history are unused.
                    for i in range(walks):
                        state[40 + 60 * walks + 8 * i + 6:40 + 60 * walks + 8 * i + 8] = b'\xff\xff'
                digest = hashlib.sha256(state).hexdigest()
                if name == 'baseline':
                    guard_reference = digest if valid and reseeded == walks else None
                ok = valid and reseeded == walks and digest == guard_reference
                row['guard_check'] = {'run': check, 'ok': ok, 'reseeded_walks': reseeded,
                                      'canonical_checkpoint_sha256': digest}
                if not ok:
                    row.update(reports_ok=False, error='overdue/reseed state differs from reference')
                    continue
            if metadata and name != "baseline":
                row["resume_checks"] = []
                # Checkpoints require equal batch geometry. With a different
                # batch, check self-continuation against the same baseline
                # corpus instead of attempting an incompatible restore.
                directions = (((name, name),) if batches[name] != batches["baseline"]
                              else (("baseline", name), (name, "baseline")))
                for first, second in directions:
                    ckpt = root / (first + "-to-" + second + ".ckpt")
                    ckpt.unlink(missing_ok=True)
                    resume_corpus = root / (first + "-to-" + second + ".bin")
                    resume_corpus.unlink(missing_ok=True)
                    checks = []
                    for part in (first, second):
                        checks.append(run([binaries[part], "--curve", "131", "--packed",
                            "--threads", str(replay_walks // batches[part]), "--dp-weight", "50", "--steps", str(replay_steps),
                            "--launches", "3", "--dp-cap", "262144", "--verify", "0",
                            "--checkpoint", str(ckpt), "--dp-file", str(resume_corpus)]))
                    data = resume_corpus.read_bytes() if resume_corpus.exists() else b""
                    digest = hashlib.sha256(b"".join(sorted(data[i:i+32] for i in range(0,len(data),32)))).hexdigest()
                    ok = (all(c["returncode"] == 0 for c in checks)
                          and "resumed from" in checks[1]["raw"]
                          and len(data) == 32 * row["corpus"]["records"]
                          and digest == row["corpus"]["sorted_sha256"])
                    row["resume_checks"].append({"from": first, "to": second, "checks": checks, "ok": ok})
                    if not ok:
                        row["reports_ok"] = False
                        row["error"] = "cross-build checkpoint continuation differs from uninterrupted walk"
                if not row["reports_ok"]:
                    continue
            accepted[name] = args + ["--bench", "--steps", "1024", "--launches", "256" if certify else "64", "--verify", "0"]
            row["warmup"] = run(accepted[name])
            result["samples"][name] = []
    for repeat in range(5 if certify else 3):
        order = list(accepted) if repeat % 2 == 0 else list(reversed(accepted))
        for name in order:
            row = run(accepted[name])
            sample = sample_result(row)
            sample["telemetry"] = run(["nvidia-smi", "--query-gpu=clocks.sm,temperature.gpu,power.draw,power.limit",
                                        "--format=csv"])
            result["samples"][name].append(sample)
    result["summary"] = {name: summarizeSamples(rows) for name, rows in result["samples"].items()}
    if certify:
        # Every collection comparison must cover the same initial walks,
        # including experiments that change only threads per block.
        collection_walks = result["samples"][certify][0]["walks"]
        for name in accepted:
            row = result["variants"][name]
            corpus = root / (name + "-collection.bin")
            collection_extra = ["--threads", str(collection_walks // batches[name])] if collection_walks else []
            collection = run([binaries[name], "--curve", "131", "--packed", "--dp-weight", "34",
                "--steps", "1024", "--launches", "256", "--verify", "0", "--dp-file", str(corpus)] + collection_extra)
            row["collection"] = sample_result(collection)
            if collection["returncode"] == 0:
                data = corpus.read_bytes()
                assert len(data) % 32 == 0
                row["collection_corpus"] = {"records": len(data) // 32,
                    "sorted_sha256": hashlib.sha256(b"".join(sorted(data[i:i+32] for i in range(0,len(data),32)))).hexdigest()}
        result["candidate_corpus_matches"] = (result["variants"].get(certify,{}).get("collection_corpus") is not None
            and result["variants"][certify]["collection_corpus"] == result["variants"]["baseline"].get("collection_corpus"))
    result["gpu"] = run(["nvidia-smi", "--query-gpu=name,uuid,clocks.sm,power.limit", "--format=csv"])
    return result
