#!/usr/bin/env python3
"""Build source-bound N83 selector masks with propagation-call counters."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
from pathlib import Path

from phase_schedule import INDICES, phases

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/Volumes/SSD990/llm/tmp/q1473_wdsat_build")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


q1472 = load("q1472_build_for_q1473", Q1472 / "build.py")


def patch_selector_and_counters(source: Path, schedule: dict[int, dict]) -> dict:
    path = source / "wdsat.c"
    content = path.read_text()
    selector_ids = sorted(set(x for phase in schedule.values() for x in phase["flip_ids"]))
    assert len(selector_ids) == 2
    anchor = "static int_t set[__ID_SIZE__];\n"
    assert content.count(anchor) == 1
    definition = f"""

/* Q1473: count propagation calls separately from left-branch attempts. */
static unsigned long long q1473_cnf_calls = 0;
static unsigned long long q1473_xor_calls = 0;
static void q1473_report_work(void) {{
    fprintf(stderr, "Q1473_WORK_FINAL %llu %llu\\n",
            q1473_cnf_calls, q1473_xor_calls);
    fflush(stderr);
}}
static void q1473_apply_selector(int_t count) {{
    const char *raw = getenv("Q1473_SELECTOR_PHASE");
    char *end = NULL;
    long phase = raw ? strtol(raw, &end, 10) : -1;
    if (!raw || !*raw || !end || *end || phase < 0 || phase > 3) {{
        fprintf(stderr, "Q1473_BAD_PHASE\\n"); fflush(stderr); exit(64);
    }}
    int seen0 = 0, seen1 = 0;
    for (int_t i = 0; i < count; ++i) {{
        int_t variable = set[i];
        if (variable == {selector_ids[0]}) {{
            seen0++;
            if (phase & 1) set[i] = -variable;
        }} else if (variable == {selector_ids[1]}) {{
            seen1++;
            if (phase & 2) set[i] = -variable;
        }}
    }}
    if (seen0 != 1 || seen1 != 1) {{
        fprintf(stderr, "Q1473_BAD_SELECTOR_ORDER\\n"); fflush(stderr); exit(64);
    }}
    if (atexit(q1473_report_work) != 0) exit(64);
    fprintf(stderr, "Q1473_SELECTOR_PHASE %ld {selector_ids[0]} {selector_ids[1]}\\n", phase);
    fflush(stderr);
}}
"""
    content = content.replace(anchor, anchor + definition)
    call = "\t\tq1472_apply_phase(nb_min_vars);\n"
    assert content.count(call) == 1
    content = content.replace(call, call + "\t\tq1473_apply_selector(nb_min_vars);\n")
    for function, counter in (("cnf_set_true", "cnf"),
                              ("xorset_set_true", "xor")):
        needle = f"if(!{function}(_l))"
        assert content.count(needle) == 2
        content = content.replace(needle, f"q1473_{counter}_calls++; {needle}")
    checkpoint = 'fprintf(stderr, "Q1464_BRANCH %lld\\n", (long long)count);'
    assert content.count(checkpoint) == 1
    content = content.replace(checkpoint, checkpoint +
        '\n        fprintf(stderr, "Q1473_WORK %lld %llu %llu\\n", '
        '(long long)count, q1473_cnf_calls, q1473_xor_calls);')
    path.write_text(content)
    return {"patch_kind": "two_selector_sign_masks_and_cnf_xor_set_true_calls",
            "selector_ids": selector_ids, "phase_masks": schedule,
            "instrumented_cnf_call_sites": 2,
            "instrumented_xor_call_sites": 2,
            "wdsat_c_sha256": sha(path)}


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_build_path = Q1472 / "build_receipt.json"
    parent_build = json.loads(parent_build_path.read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["q1472_build_source_sha256"] == sha(Q1472 / "build.py")
    assert freeze["q1472_build_receipt_sha256"] == sha(parent_build_path)
    assert freeze["phase_source_sha256"] == sha(HERE / "phase_schedule.py")
    assert freeze["phase_schedule"] == {str(i): phases()[i] for i in INDICES}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM).strip()
    BUILD.mkdir()
    source = BUILD / "n83/src"
    shutil.copytree(UPSTREAM / "src", source)
    caps = parent_build["config"]
    config = source / "config.h"
    config.write_text("/* Q1473 exact Q1472 N83 width-four limits. */\n" +
                      "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
    storage = q1472.prior.patch_quadratic_undo_storage(source)
    markers = q1472.prior.instrument_search(source)
    branch = q1472.prior.patch_branch_work(
        source, protocol["limits"]["left_branch_attempts_per_phase"])
    order = q1472.order_builder.patch_order(source, 83)
    prior_phase = q1472.patch_phase(source, phases())
    selector = patch_selector_and_counters(source, phases())
    make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                          capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(make.stdout)
    (HERE / "build.stderr.txt").write_text(make.stderr)
    binary = BUILD / "n83/wdsat_solver"
    output = {"proposal_id": "Q1473", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "config": caps, "config_sha256": sha(config),
              "storage_patch": storage, "search_markers": markers,
              "branch_patch": branch, "order_patch": order,
              "q1472_phase_patch": prior_phase, "selector_patch": selector,
              "source_tree_sha256": q1472.prior.tree_sha(source),
              "return_code": make.returncode,
              "binary_path": str(binary) if binary.exists() else None,
              "binary_sha256": sha(binary) if binary.exists() else None,
              "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
              "build_stderr_sha256": sha(HERE / "build.stderr.txt")}
    assert make.returncode == 0 and binary.exists(), make.stderr[-2000:]
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1473 built", output["binary_sha256"][:12])


if __name__ == "__main__":
    main()
