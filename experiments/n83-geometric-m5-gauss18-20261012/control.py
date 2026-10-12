#!/usr/bin/env python3
"""Replay the frozen width-18 locked relation with one Gaussian matrix."""

import importlib.util
import json
from pathlib import Path

from pilot import HERE, PARENT, runner


def main():
    spec = importlib.util.spec_from_file_location(
        "parent_gauss_control", PARENT / "control.py")
    control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    original = control.runner.solve_limited
    wrapper = HERE / "gauss_one.sh"
    assert runner.sha(wrapper) == json.loads((HERE / "protocol.json").read_text())[
        "solvers"]["gauss"]["sha256"]

    def tuned(path, binary, seconds, max_conflicts, rss_cap):
        return original(path, wrapper, seconds, max_conflicts, rss_cap)

    control.HERE = HERE
    control.runner.solve_limited = tuned
    try:
        control.main()
    finally:
        control.runner.solve_limited = original
    path = HERE / "karatsuba_control.json"
    receipt = json.loads(path.read_text())
    receipt["solver_variant"] = "gauss"
    receipt["control_wrapper_source_sha256"] = runner.sha(Path(__file__))
    receipt["solver_wrapper_sha256"] = runner.sha(wrapper)
    runner.save(path, receipt)


if __name__ == "__main__":
    main()
