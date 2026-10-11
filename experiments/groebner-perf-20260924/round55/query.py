"""Independent proof checking for every speculative pair-pruning variant."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent/'round11'
sys.path.insert(0,str(P))
from packed_proof import anf_from_equations
NAMES=('mode','candidate_pairs','scanned_leaders','eligible_chains','pruned_pairs','represented_pairs_skipped','field_pairs','probes','probe_zero','probe_nonzero','probe_soft_limits','probe_aborted','probe_work','peak_probe_nodes','cache_hits','product_hits','failed_probe_hits','represented_entries','failed_entries','cache_saturated','raw_zero_pairs','overhead_work')
class ChainStats(C.Structure):
    _fields_=[(name,C.c_uint64) for name in NAMES]
class Query:
    def __init__(self,variant='probe',sanitizer=False):
        if variant not in ('prior','disabled','probe','cached','tiny_probe','tiny_cache'): raise ValueError('unknown variant')
        spec=importlib.util.spec_from_file_location('checked_chain55_'+variant,P/'packed_proof.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.HERE=HERE/'build'/variant
        self.base=module.PackedProof(sanitizer=sanitizer)
        self.variant=variant
        self.binary_sha256=self.base.binary_sha256
        if variant!='prior':
            lib=self.base.producer
            lib.producer_chain_stats_size.restype=C.c_uint64
            assert lib.producer_chain_stats_size()==C.sizeof(ChainStats)
            lib.producer_chain_stats.restype=C.POINTER(ChainStats)
    def compute(self,*args,**kwargs):
        result=self.base.compute(*args,**kwargs)
        if self.variant!='prior':
            stats=self.base.producer.producer_chain_stats().contents
            result['chain_stats']={name:getattr(stats,name) for name in NAMES}
        return result
