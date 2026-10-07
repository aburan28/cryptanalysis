"""Synchronous leased packed input through the unchanged producer and new checker."""
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('live94_for95',P/'round94/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
previous.HERE=HERE
previous.previous.HERE=HERE
previous.previous.previous.HERE=HERE
previous.abi.HERE=HERE
abi=previous.abi
sys.path.insert(0,str(P/'round60'))
from input_plan import BorrowedInput,InputWorkspace,PackedDescentPlan

ARMS={'legacy':('legacy','baseline'),'completion':('completion-first','baseline'),
      'release-cumulative':('completion-first','release-cumulative'),'release-live':('completion-first','release-live')}

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,arm='legacy'):
        if arm not in ARMS:raise ValueError('unknown complete-query arm')
        self.arm=arm
        order,retention=ARMS[arm]
        super().__init__(sanitizer=sanitizer,checker_order=order,retention=retention)
    def workspace(self,nvars,equations,support):
        return InputWorkspace(nvars,equations,support,view_type=abi.PackedInput)
    def compute(self,original,**kwargs):
        if not isinstance(original,BorrowedInput):raise ValueError('complete-query transport requires a live input lease')
        original.validate(view_type=abi.PackedInput)
        return super().compute(original,**kwargs)
