"""Build the unchanged round94 checker for the complete-query comparison."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent

def source():
    spec=importlib.util.spec_from_file_location('liveness94_for95_build',HERE.parent/'round94/generate.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    return old.source()
