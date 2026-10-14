#!/usr/bin/env python3
"""Run the locked relation control for the length-21 materialization."""

import importlib.util

from partial import HERE, FLAT, build

spec = importlib.util.spec_from_file_location("flat_control", FLAT / "control.py")
flat_control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flat_control)


def main():
    flat_control.HERE = HERE
    flat_control.build = lambda onb, target_x, choice: build(
        onb, target_x, 21, choice)
    flat_control.main()


if __name__ == "__main__":
    main()
