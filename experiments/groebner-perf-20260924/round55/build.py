"""Build a bounded, explicitly checked chain criterion over the cached F4 engine."""
import hashlib,importlib.util,json,os,platform,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
P=HERE.parent

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def replace_once(source,old,new):
    assert source.count(old)==1,old
    return source.replace(old,new)
def cached_source():
    old=P/'round12/native_engine.cpp'
    assert sha(old)=='3153861f2fb9ecc0e07bdff29bf196bc4e7444e10c4989fc4e180afee3378c67'
    s=old.read_text();start=s.index('    Row normal(');end=s.index('#else',start)
    s=s[:start]+(P/'round13/normal_frontier.inc').read_text()+s[end:]
    spec=importlib.util.spec_from_file_location('cache_transform55',P/'round13/cache_transform.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.cached_engine(s)
def main():
    out=HERE/'build';out.mkdir(exist_ok=True)
    prior=cached_source()
    (out/'cached.inc').write_text(prior)
    s=replace_once(prior,'    void install(Row row) {',(HERE/'checked_chains.inc').read_text()+'\n    void install(Row row) {')
    s=replace_once(s,'                Row row;\n                if (p.field)',
        '                if (CHECKED_CHAIN_MODE && !p.field && chain_prune(p)) continue;\n'
        '                if (CHECKED_CHAIN_MODE && p.field) ++chain_stats.field_pairs;\n'
        '                Row row;\n                if (p.field)')
    s=replace_once(s,'                if (!row.terms.empty()) batch.push_back(std::move(row));',
        '                if (CHECKED_CHAIN_MODE && !p.field && row.terms.empty()) {\n'
        '                    ++chain_stats.raw_zero_pairs; chain_remember(p.i,p.j);\n'
        '                }\n                if (!row.terms.empty()) batch.push_back(std::move(row));')
    (out/'checked.inc').write_text('#include "../chain_stats.h"\n'+s)
    adapter=(P/'round11/packed_producer.cpp').read_text()
    marker='#include "build/native_engine.inc"'
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    compiler=os.environ.get('CXX','clang++');commands=[]
    variants={'prior':None,'disabled':0,'probe':1,'cached':2,'tiny_probe':1,'tiny_cache':1}
    for variant,mode in variants.items():
        directory=out/variant/'build';directory.mkdir(parents=True,exist_ok=True)
        engine='cached.inc' if mode is None else 'checked.inc'
        source=replace_once(adapter,marker,'#include "../../'+engine+'"')
        if mode is not None:
            source=replace_once(source,'auto start=Clock::now();failure.clear();','auto start=Clock::now();failure.clear();chain_stats={};chain_stats.mode=CHECKED_CHAIN_MODE;')
            source+='\nextern "C" uint64_t producer_chain_stats_size(){return sizeof(ChainStats);}\nextern "C" const ChainStats* producer_chain_stats(){return &chain_stats;}\n'
        path=directory/'adapter.cpp';path.write_text(source)
        extra=[] if mode is None else [f'-DCHECKED_CHAIN_MODE={mode}']
        if variant=='tiny_probe': extra+=['-DCHAIN_PROBE_WORK=8']
        if variant=='tiny_cache': extra+=['-DCHAIN_CACHE_LIMIT=1']
        for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
            cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,'-I',str(P/'round11'),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',*extra,str(path),'-o',str(directory/('packed_producer'+tag+suffix))]
            subprocess.run(cmd,check=True);commands.append(cmd)
        print('BUILT',variant,flush=True)
    for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        binary=out/('native_checker'+tag+suffix)
        cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,str(P/'round11/native_checker.cpp'),'-o',str(binary)]
        subprocess.run(cmd,check=True);commands.append(cmd)
        for variant in variants:
            link=out/variant/'build'/binary.name
            if not link.exists(): link.symlink_to('../../'+binary.name)
    sources=[*HERE.glob('*.py'),*HERE.glob('*.cpp'),*HERE.glob('*.h'),*HERE.glob('*.inc'),P/'round12/native_engine.cpp',P/'round13/cache_transform.py',P/'round13/normal_frontier.inc',*[P/'round11'/name for name in ('proof_abi.h','packed_producer.cpp','native_checker.cpp','packed_proof.py')]]
    receipt={'commands':commands,'sources':{str(p.relative_to(P)):sha(p) for p in sources},'binaries':{str(p.relative_to(out)):sha(p) for p in out.rglob('*'+suffix)},'generated':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.suffix in ('.cpp','.inc')},'compiler':subprocess.check_output([compiler,'--version'],text=True),'platform':platform.platform(),'architecture':platform.machine()}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__': main()
