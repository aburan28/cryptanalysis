"""Packed ordering keys confined to ordered_multiple temporary rows."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def source():return load('checker95_for98',P/'round95/generate.py').source()

def producer_source(enabled,minimum):
    old=load('producer62_for98',P/'round62/native_build.py')
    s=old.source(8388608)
    s=old.change(s,'#include "../../../../../round55/chain_stats.h"','#include "chain_stats.h"')
    s='#include "monomial_order.h"\n'+s
    begin=s.index('    Row ordered_multiple(')
    end=s.index('    Row ordered_add(',begin)
    original=s[begin:end]
    anchor='std::sort(out.begin(),out.end(),[](Mask a,Mask b){return less_monomial(b,a);});'
    candidate=old.change(original,anchor,
        f'sort_ordered_terms(out,[](Mask a,Mask b){{return less_monomial(b,a);}},'+('true' if enabled else 'false')+f',{minimum});')
    # The unchanged source method is compiled only by the direct native tests.
    reference='#ifdef ORDER_TEST_REFERENCE\n'+original.replace('Row ordered_multiple(', 'Row reference_multiple(')+'#endif\n'
    return s[:begin]+reference+candidate+s[end:]

def adapter_source(engine):
    old=load('adapter62_for98',P/'round62/native_build.py')
    s=(P/'round11/packed_producer.cpp').read_text()
    s=old.change(s,'#include "build/native_engine.inc"',f'#include "{engine}"')
    s=old.change(s,'auto start=Clock::now();failure.clear();',
        'auto start=Clock::now();failure.clear();top_stats={};column_stats={};scratch_stats={};packed_stats={};chain_stats={};chain_stats.mode=1;monomial_order_stats={};')
    s+='\nextern "C" uint64_t producer_order_stats_size(){return sizeof(MonomialOrderStats);}\n'
    s+='extern "C" const MonomialOrderStats* producer_order_stats(){return &monomial_order_stats;}\n'
    return s
