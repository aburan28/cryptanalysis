"""Frozen complete-query descent and independent replay for storage variants."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('common95_for99',HERE.parent/'round95/common.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
Context=previous.Context
fixtures=previous.fixtures
plan=previous.plan
digest=previous.digest
