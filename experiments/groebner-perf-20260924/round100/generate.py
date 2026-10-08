"""Rebuild unchanged round99 kernels for the larger completion panel."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('generate99_for100',Path(__file__).resolve().parent.parent/'round99/generate.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
source=previous.source
producer_source=previous.producer_source
adapter_source=previous.adapter_source
