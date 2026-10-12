#!/usr/bin/env python3
"""Build pinned plain WDSat with source-bound phase restarts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from phase_schedule import INDICES, phases

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"
Q1469 = PARENT / "q20261011_wdsat_prefix_search"
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/Volumes/SSD990/llm/tmp/q1472_wdsat_build")
sys.path.insert(0, str(Q1469))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("q1464_build_for_q1472", Q1464 / "build.py")
order_builder = load("q1469_build_for_q1472", Q1469 / "build.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_phase(source: Path, schedule: dict[int, dict]) -> dict:
    path = source / "wdsat.c"
    content = path.read_text()
    anchor = "static int_t set[__ID_SIZE__];\n"
    assert content.count(anchor) == 1
    arrays = "\n".join(
        f"static const int_t q1472_phase_{index}[] = " +
        "{" + ", ".join(map(str, schedule[index]["flip_ids"])) + "};"
        for index in INDICES[1:])
    choices = "\n".join(
        f"    case {index}: flips = q1472_phase_{index}; "
        f"length = sizeof(q1472_phase_{index}) / sizeof(q1472_phase_{index}[0]); break;"
        for index in INDICES[1:])
    definition = f"""

/* Q1472: change only first-branch polarity; every variable remains present. */
{arrays}
static unsigned char q1472_flip[__ID_SIZE__];
static void q1472_apply_phase(int_t count) {{
    const char *raw = getenv("Q1472_PHASE_INDEX");
    char *end = NULL;
    long index = raw ? strtol(raw, &end, 10) : -1;
    if (!raw || !*raw || !end || *end || index < 0 || index > 8) {{
        fprintf(stderr, "Q1472_BAD_PHASE\\n"); fflush(stderr); exit(64);
    }}
    const int_t *flips = NULL;
    size_t length = 0;
    switch (index) {{
    case 0: break;
{choices}
    default: fprintf(stderr, "Q1472_BAD_PHASE\\n"); fflush(stderr); exit(64);
    }}
    for (size_t i = 0; i < length; ++i) {{
        int_t variable = flips[i];
        if (variable < 1 || variable > count || q1472_flip[variable]) {{
            fprintf(stderr, "Q1472_BAD_FLIP_ID\\n"); fflush(stderr); exit(64);
        }}
        q1472_flip[variable] = 1;
    }}
    size_t changed = 0;
    for (int_t i = 0; i < count; ++i) {{
        int_t variable = set[i];
        if (variable < 1 || variable > count) {{
            fprintf(stderr, "Q1472_BAD_ORDER_ID\\n"); fflush(stderr); exit(64);
        }}
        if (q1472_flip[variable]) {{ set[i] = -variable; changed++; }}
    }}
    if (changed != length) {{
        fprintf(stderr, "Q1472_BAD_PHASE_COUNT\\n"); fflush(stderr); exit(64);
    }}
    fprintf(stderr, "Q1472_PHASE %ld %lld\\n", index, (long long)length);
    fflush(stderr);
}}
"""
    content = content.replace(anchor, anchor + definition)
    call = "\t\tq1469_apply_order(nb_min_vars);\n"
    assert content.count(call) == 1
    content = content.replace(call, call + "\t\tq1472_apply_phase(nb_min_vars);\n")
    path.write_text(content)
    return {"patch_kind": "signed_variable_first_branch_polarity",
            "phase_count": len(schedule),
            "flip_counts": {str(index): len(schedule[index]["flip_ids"])
                            for index in INDICES},
            "wdsat_c_sha256": sha(path)}


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_build_path = Q1469 / "build_receipt.json"
    parent_build = json.loads(parent_build_path.read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["phase_source_sha256"] == sha(HERE / "phase_schedule.py")
    assert freeze["q1469_build_receipt_sha256"] == sha(parent_build_path)
    assert freeze["q1469_build_source_sha256"] == sha(Q1469 / "build.py")
    assert freeze["q1464_build_source_sha256"] == sha(Q1464 / "build.py")
    schedule = phases()
    assert freeze["phase_schedule"] == {str(index): schedule[index]
                                         for index in INDICES}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM).strip()
    cap = protocol["limits"]["left_branch_attempts_per_phase"]
    assert cap == 1 << 20
    BUILD.mkdir()
    source = BUILD / "n83/src"
    shutil.copytree(UPSTREAM / "src", source)
    caps = parent_build["per_degree"]["n83"]["config"]
    config = source / "config.h"
    config.write_text("/* Q1472 exact Q1469 N83 width-four limits. */\n" +
                      "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
    storage = prior.patch_quadratic_undo_storage(source)
    markers = prior.instrument_search(source)
    branch = prior.patch_branch_work(source, cap)
    order = order_builder.patch_order(source, 83)
    phase = patch_phase(source, schedule)
    make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                          capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(make.stdout)
    (HERE / "build.stderr.txt").write_text(make.stderr)
    binary = BUILD / "n83/wdsat_solver"
    output = {"proposal_id": "Q1472", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "config": caps, "config_sha256": sha(config),
              "storage_patch": storage, "search_markers": markers,
              "branch_patch": branch, "order_patch": order,
              "phase_patch": phase,
              "source_tree_sha256": prior.tree_sha(source),
              "return_code": make.returncode,
              "binary_path": str(binary) if binary.exists() else None,
              "binary_sha256": sha(binary) if binary.exists() else None,
              "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
              "build_stderr_sha256": sha(HERE / "build.stderr.txt")}
    assert make.returncode == 0 and binary.exists(), make.stderr[-2000:]
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1472 built", output["binary_sha256"][:12])


if __name__ == "__main__":
    main()
