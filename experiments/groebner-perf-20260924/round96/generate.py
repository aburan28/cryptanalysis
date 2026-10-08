"""Attach diagnostic scopes without changing producer arithmetic or limits."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE.parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def source():return load('checker95_for96',P/'round95/generate.py').source()

def producer_source():
    old=load('producer62_for96',P/'round62/native_build.py')
    s=old.source(8388608)
    s=old.change(s,'#include "../../../../../round55/chain_stats.h"','#include "chain_stats.h"')
    s='#include "profile.h"\n'+s
    s=old.change(s,'        work += amount;','        work += amount;\n        profile_charge(amount);')
    s=old.change(s,'            work=max_work;','            profile_charge(max_work-work);\n            work=max_work;')
    s=old.change(s,'        work+=a*b;','        work+=a*b;\n        profile_charge(a*b);')
    signatures={
        'Canonical':'    Poly canonical(Poly terms) {',
        'Multiply':'    Row multiply(const Row& row,Mask mask) {',
        'Add':'    Row add(const Row& a,const Row& b) {',
        'OrderedMultiple':'    Row ordered_multiple(const Row& row,Mask mask) {',
        'OrderedAdd':'    Row ordered_add(const Row& a,const Row& b) {',
        'Install':'    void install(Row row) {',
        'Chain':'    bool chain_prune(const Pair &pair) {',
        'Symbolic':'    std::vector<Row> matrix(std::vector<Row> rows) {',
        'Column':'                                   const std::set<Mask>& reducer_heads) {',
        'Packed':'                                      const std::set<Mask> &reducer_heads, size_t width)\n{',
        'Compute':'    void compute(const std::vector<Poly>& input) {',
        'Compaction':'    void compact() {',
    }
    for stage,anchor in signatures.items():
        s=old.change(s,anchor,anchor+'\n        WorkScope profile_scope(WorkStage::'+stage+', work);')
    anchor='    Row normal(Row value,const std::vector<Row>& reducers,size_t skip=SIZE_MAX) {'
    assert s.count(anchor)==2
    s=s.replace(anchor,anchor+'\n        WorkScope profile_scope(WorkStage::Normal, work);')
    s=old.change(s,'        ++packed_stats.fallback_matrices;',
        '        ++packed_stats.fallback_matrices;\n        WorkScope sparse_profile_scope(WorkStage::Sparse, work);')
    anchor='        // Sparse row echelon form: pivot monomials stand in for matrix columns.'
    s=old.change(s,anchor,anchor+'\n        WorkScope sparse_profile_scope(WorkStage::Sparse, work);')
    return s

def adapter_source():
    old=load('adapter62_for96',P/'round62/native_build.py')
    s=(P/'round11/packed_producer.cpp').read_text()
    s=old.change(s,'#include "build/native_engine.inc"','#include "profiled_engine.inc"')
    s=old.change(s,'auto start=Clock::now();failure.clear();',
        'auto start=Clock::now();failure.clear();top_stats={};column_stats={};scratch_stats={};packed_stats={};chain_stats={};chain_stats.mode=1;work_profile={};')
    for label,kind in (('top','Top'),('column','Column'),('chain','Chain'),('scratch','Scratch'),('packed','Packed'),('work','WorkProfile')):
        cpp=kind if kind=='WorkProfile' else kind+'Stats'
        variable='work_profile' if label=='work' else label+'_stats'
        s+=f'\nextern "C" uint64_t producer_{label}_stats_size(){{return sizeof({cpp});}}\n'
        s+=f'extern "C" const {cpp}* producer_{label}_stats(){{return &{variable};}}\n'
    return s
