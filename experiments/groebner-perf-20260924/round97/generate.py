"""Bounded ordered-merge storage over the unchanged packed producer."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def source():return load('checker95_for97',P/'round95/generate.py').source()

def producer_source(cap):
    old=load('producer62_for97',P/'round62/native_build.py')
    s=old.source(8388608)
    s=old.change(s,'#include "../../../../../round55/chain_stats.h"','#include "chain_stats.h"')
    s='#include "normal_scratch.h"\n'+s
    anchor='    Row ordered_add(const Row& a,const Row& b) {'
    s=old.change(s,anchor,(HERE/'normal_scratch.inc').read_text()+'\n'+anchor)
    s=old.change(s,'        size_t prefix=0;','        Poly normal_scratch;\n        size_t prefix=0;')
    anchor='                    value=ordered_add(value,ordered_multiple(reducers[i],term&~leads[i]));'
    assert s.count(anchor)==2
    s=s.replace(anchor,f'                    ordered_scratch_add(value,ordered_multiple(reducers[i],term&~leads[i]),normal_scratch,{cap});')
    return s

def adapter_source(engine):
    old=load('adapter62_for97',P/'round62/native_build.py')
    s=(P/'round11/packed_producer.cpp').read_text()
    s=old.change(s,'#include "build/native_engine.inc"',f'#include "{engine}"')
    s=old.change(s,'auto start=Clock::now();failure.clear();',
        'auto start=Clock::now();failure.clear();top_stats={};column_stats={};scratch_stats={};packed_stats={};chain_stats={};chain_stats.mode=1;normal_scratch_stats={};')
    s+='\nextern "C" uint64_t producer_normal_stats_size(){return sizeof(NormalScratchStats);}\n'
    s+='extern "C" const NormalScratchStats* producer_normal_stats(){return &normal_scratch_stats;}\n'
    return s
