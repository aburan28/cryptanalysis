"""Opt-in ordered-merge storage over the unchanged leased query/checker API."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('query95_for97',P/'round95/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
module=previous
while module is not None:
    module.HERE=HERE
    if hasattr(module,'abi'):module.abi.HERE=HERE
    module=getattr(module,'previous',None)
abi=previous.abi;PackedDescentPlan=previous.PackedDescentPlan
ARMS={'baseline':None,'fresh':0,'scratch':32768,'tiny':4}
NAMES=('calls','completed','charged_terms','fresh_vectors','growths','reused','oversized_releases','released_capacity_words','peak_scratch_capacity','peak_retained_scratch_capacity','overflow')
class NormalStats(C.Structure):_fields_=[(name,abi.U64) for name in NAMES]

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,arm='baseline'):
        if arm not in ARMS:raise ValueError('unknown normal storage policy')
        super().__init__(sanitizer=sanitizer,arm='legacy');self.arm=arm
        if arm!='baseline':
            suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
            path=HERE/'build'/('normal_'+arm+suffix);library=C.CDLL(str(path))
            for name in ('produce_packed','producer_view','producer_destroy','producer_error'):
                new=getattr(library,name);old=getattr(self.base.producer,name);new.argtypes=old.argtypes;new.restype=old.restype
            self.base.producer=library;self.binary_sha256[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            library.producer_normal_stats_size.argtypes=[];library.producer_normal_stats_size.restype=abi.U64
            assert library.producer_normal_stats_size()==C.sizeof(NormalStats)
            library.producer_normal_stats.argtypes=[];library.producer_normal_stats.restype=C.POINTER(NormalStats)

    def compute(self,*args,**kwargs):
        result=super().compute(*args,**kwargs);result['normal_storage_policy']=self.arm
        if self.arm!='baseline':
            stats=self.base.producer.producer_normal_stats().contents
            result['normal_scratch']={name:int(getattr(stats,name)) for name in NAMES}
        return result
