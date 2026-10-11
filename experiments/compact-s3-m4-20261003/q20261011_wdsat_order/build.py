#!/usr/bin/env python3
"""Compile pinned WDSat with two source-bound full branch permutations."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"
Q1466 = PARENT / "q20261011_wdsat_deep_plain"
UPSTREAM = Path("/private/tmp/wdsat-q1458")
BUILD = Path("/Volumes/SSD990/llm/tmp/q1467_wdsat_build")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("q1464_build_for_q1467", Q1464 / "build.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_order(source: Path, priorities: dict[str, list[int]]) -> dict:
    path = source / "wdsat.c"
    content = path.read_text()
    anchor = "static int_t set[__ID_SIZE__];\n"
    assert content.count(anchor) == 1
    selector = priorities["selector_first"]
    interleaved = priorities["interleaved_leaves"]
    assert selector and interleaved
    assert len(selector) == len(set(selector))
    assert len(interleaved) == len(set(interleaved))
    definition = f"""

/* Q1467: a prefix permutation followed by every remaining variable. */
static const int_t q1467_selector[] = {{{', '.join(map(str, selector))}}};
static const int_t q1467_interleaved[] = {{{', '.join(map(str, interleaved))}}};
static unsigned char q1467_seen[__ID_SIZE__];
static void q1467_apply_order(int_t count) {{
    const char *mode = getenv("Q1467_ORDER_MODE");
    const int_t *priority = NULL;
    size_t length = 0;
    if (mode && strcmp(mode, "selector_first") == 0) {{
        priority = q1467_selector;
        length = sizeof(q1467_selector) / sizeof(q1467_selector[0]);
    }} else if (mode && strcmp(mode, "interleaved_leaves") == 0) {{
        priority = q1467_interleaved;
        length = sizeof(q1467_interleaved) / sizeof(q1467_interleaved[0]);
    }} else {{
        fprintf(stderr, "Q1467_BAD_ORDER\\n"); fflush(stderr); exit(64);
    }}
    int_t position = 0;
    for (size_t i = 0; i < length; ++i) {{
        int_t variable = priority[i];
        if (variable < 1 || variable > count || q1467_seen[variable]) {{
            fprintf(stderr, "Q1467_BAD_PRIORITY\\n"); fflush(stderr); exit(64);
        }}
        q1467_seen[variable] = 1;
        set[position++] = variable;
    }}
    for (int_t variable = 1; variable <= count; ++variable)
        if (!q1467_seen[variable]) set[position++] = variable;
    if (position != count) {{
        fprintf(stderr, "Q1467_BAD_PERMUTATION\\n"); fflush(stderr); exit(64);
    }}
    fprintf(stderr, "Q1467_ORDER %s %lld\\n", mode, (long long)length);
    fflush(stderr);
}}
"""
    content = content.replace(anchor, anchor + definition)
    old = "\t\tfor(j = 1; j <= nb_min_vars; j++)\n\t\t{\n\t\t\tset[j - 1] = j;\n\t\t}\n"
    assert content.count(old) == 1
    content = content.replace(old, old + "\t\tq1467_apply_order(nb_min_vars);\n")
    path.write_text(content)
    return {"patch_kind": "priority_prefix_then_complete_ascending_permutation",
            "selector_priority_count": len(selector),
            "interleaved_priority_count": len(interleaved),
            "wdsat_c_sha256": sha(path)}


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    freeze_path = HERE / "freeze.json"
    freeze = json.loads(freeze_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    manifest_path = HERE / "order_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    q1466_build_path = Q1466 / "build_receipt.json"
    q1466_build = json.loads(q1466_build_path.read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["order_manifest_sha256"] == sha(manifest_path)
    assert freeze["q1466_build_receipt_sha256"] == sha(q1466_build_path)
    assert freeze["q1464_build_source_sha256"] == sha(Q1464 / "build.py")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM,
                                     text=True).strip()
    assert commit == freeze["upstream_commit"] == protocol["solver"]["upstream_commit"]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=UPSTREAM).strip()
    cap = protocol["limits"]["left_branch_attempts_per_run"]
    assert cap == 1 << 20
    BUILD.mkdir()
    output = {"proposal_id": "Q1467", "candidate_id": None,
              "freeze_sha256": sha(freeze_path), "upstream_commit": commit,
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "per_degree": {}}
    for name in ("n53", "n83"):
        destination = BUILD / name
        source = destination / "src"
        shutil.copytree(UPSTREAM / "src", source)
        caps = q1466_build["per_degree"][name]["config"]
        config = source / "config.h"
        config.write_text("/* Q1467 exact Q1466 width-four limits. */\n" +
                          "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
        storage = prior.patch_quadratic_undo_storage(source)
        markers = prior.instrument_search(source)
        branch = prior.patch_branch_work(source, cap)
        data = manifest["cells"][name]
        order = patch_order(source, {"selector_first": data["selector_priority"],
                                     "interleaved_leaves": data["interleaved_leaves_priority"]})
        make = subprocess.run(["make", "-f", "makefile"], cwd=source,
                              capture_output=True, text=True)
        (HERE / f"build_{name}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{name}.stderr.txt").write_text(make.stderr)
        binary = destination / "wdsat_solver"
        output["per_degree"][name] = {
            "config": caps, "config_sha256": sha(config),
            "storage_patch": storage, "search_markers": markers,
            "branch_patch": branch, "order_patch": order,
            "source_tree_sha256": prior.tree_sha(source),
            "return_code": make.returncode,
            "binary_path": str(binary) if binary.exists() else None,
            "binary_sha256": sha(binary) if binary.exists() else None,
            "build_stdout_sha256": sha(HERE / f"build_{name}.stdout.txt"),
            "build_stderr_sha256": sha(HERE / f"build_{name}.stderr.txt")}
        assert make.returncode == 0 and binary.exists(), make.stderr[-2000:]
        print(name, "built", output["per_degree"][name]["binary_sha256"][:12])
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
