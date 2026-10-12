"""Opt-in monomial sorting over the unchanged leased query/checker API."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('query95_for99',P/'round95/query.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
module=previous
while module is not None:
    module.HERE=HERE
    if hasattr(module,'abi'):module.abi.HERE=HERE
    module=getattr(module,'previous',None)
abi=previous.abi;PackedDescentPlan=previous.PackedDescentPlan
ARMS={'baseline':None,'keys':None,'radix':32768,'tiny':256}
NAMES=('calls','terms','key_calls','key_terms','comparison_calls','comparison_terms','disabled_calls','small_calls','wide_calls','overflow')
RADIX_NAMES=('calls','terms','radix_calls','radix_terms','key_fallbacks','small_fallbacks','wide_fallbacks','cap_fallbacks','capacity_fallbacks','growths','reused','passes','skipped_passes','scatter_terms','copyback_terms','peak_capacity','peak_transient_capacity','oversized_releases','overflow')
class RadixStats(C.Structure):_fields_=[(name,abi.U64) for name in RADIX_NAMES]
class OrderStats(C.Structure):_fields_=[(name,abi.U64) for name in NAMES]

class Query(previous.Query):
    def __init__(self,*,sanitizer=False,arm='baseline'):
        if arm not in ARMS:raise ValueError('unknown monomial sort policy')
        super().__init__(sanitizer=sanitizer,arm='legacy');self.arm=arm
        if arm!='baseline':
            suffix=('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
            path=HERE/'build'/('radix_'+arm+suffix);library=C.CDLL(str(path))
            for name in ('produce_packed','producer_view','producer_destroy','producer_error'):
                new=getattr(library,name);old=getattr(self.base.producer,name);new.argtypes=old.argtypes;new.restype=old.restype
            self.base.producer=library;self.binary_sha256[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            library.producer_order_stats_size.argtypes=[];library.producer_order_stats_size.restype=abi.U64
            assert library.producer_order_stats_size()==C.sizeof(OrderStats)
            library.producer_order_stats.argtypes=[];library.producer_order_stats.restype=C.POINTER(OrderStats)
            library.producer_radix_stats_size.argtypes=[];library.producer_radix_stats_size.restype=abi.U64
            assert library.producer_radix_stats_size()==C.sizeof(RadixStats)
            library.producer_radix_stats.argtypes=[];library.producer_radix_stats.restype=C.POINTER(RadixStats)

    def compute(self,*args,**kwargs):
        result=super().compute(*args,**kwargs);result['monomial_sort_policy']=self.arm
        if self.arm!='baseline':
            stats=self.base.producer.producer_order_stats().contents
            result['monomial_order']={name:int(getattr(stats,name)) for name in NAMES}
            if self.arm!='keys':
                radix=self.base.producer.producer_radix_stats().contents
                result['monomial_radix']={name:int(getattr(radix,name)) for name in RADIX_NAMES}
        return result
