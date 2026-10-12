"""Reuse the exact validated round102 numerical source generators."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('generator102_for103', HERE.parent/'round102/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source = previous.source
sparse_source = previous.sparse_source
dense_source = previous.dense_source
