"""Bounded radix sorting over the unchanged round98 integer-order representation."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def source():return load('checker95_for99',P/'round95/generate.py').source()

def producer_source(cap):
    previous=load('order98_for99',P/'round98/generate.py')
    old=load('producer62_for99',P/'round62/native_build.py')
    s=previous.producer_source(True,0)
    s='#include "monomial_radix.h"\n'+s
    if cap is not None:
        s=old.change(s,'class Engine {\npublic:', 'class Engine {\npublic:\n    Poly radix_scratch;')
        s=old.change(s,'sort_ordered_terms(out,[](Mask a,Mask b){return less_monomial(b,a);},true,0);',
            f'sort_radix_terms(out,[](Mask a,Mask b){{return less_monomial(b,a);}},radix_scratch,128,{cap});')
    return s

def adapter_source(engine):
    previous=load('adapter98_for99',P/'round98/generate.py')
    s=previous.adapter_source(engine)
    assert s.count('monomial_order_stats={};')==1
    s=s.replace('monomial_order_stats={};','monomial_order_stats={};monomial_radix_stats={};')
    s+='\nextern "C" uint64_t producer_radix_stats_size(){return sizeof(MonomialRadixStats);}\n'
    s+='extern "C" const MonomialRadixStats* producer_radix_stats(){return &monomial_radix_stats;}\n'
    return s
