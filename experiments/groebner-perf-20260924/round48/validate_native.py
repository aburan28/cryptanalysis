"""Frozen corpus and fresh complete queries; no elapsed-time performance claim."""
import argparse,base64,gzip,hashlib,json,platform,sys
from contextlib import ExitStack
from pathlib import Path
from test_symmetry import HERE,ORIGINAL,candidate,producer,accepted_checker,truth,integers
from tagged_reference import certify_roots
from quadratic_reference import verify_basis
from adapter import IdentityQuery as NormalizedQuery
from transform_accounting import reconcile_transform
from identity_accounting import CONTROL_VARIANTS, QUERY_VARIANTS, reconcile_identity, equivalent_stats, per_record
from public_replay import Point


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())

def reconcile(new,old,x,y,e,oracle=None):
 reconcile_transform(new,x,y,e,audit=False)
 reconcile_identity(new,x,y,e,audit=False)
 assert new['verified'] and old['verified'],(new,old)
 n,o,s,pn,po=new['stats'],old['stats'],new['symmetry_check_stats'],new['partial_stats'],old['partial_stats']
 for key in ('branches','contradictions','enumerated_branches','roots','standard','work','workspace_bytes','proof_bytes','extended_contradictions'):
  assert n[key]==o[key],(key,n[key],o[key])
 assert n['assignments']+s['avoided_assignments']==o['assignments']
 assert new['identity_check_stats']['dense_equivalent_parities']+s['multiplier_aliases']*per_record(y,e,0)['parities']==o['multiplier_parities']
 assert pn['records']+s['partial_aliases']==po['records']
 assert pn['rank_sum']+s['derived_partial_rank']==po['rank_sum']
 assert pn['inconsistent']+s['derived_partial_inconsistent']==po['inconsistent']
 assert pn['assignments']+s['derived_partial_assignments']==po['assignments']
 assert s['inferred_aliases']==s['representatives']
 assert s['inferred_aliases']==sum(s[k] for k in ('constant_aliases','multiplier_aliases','partial_aliases','enumerated_aliases'))
 assert s['work']<=67108864 and s['workspace_bytes']<=8388608
 if not s['enabled']:
  assert integers(equivalent_stats(new))==integers(o)
  assert integers(pn)==integers(po)
 if oracle is not None:
  roots,constants,extended,partials,assignments=oracle
  assert new['solutions']==list(roots)
  assert o['assignments']==assignments
  assert o['contradictions']==constants+len(extended)+sum(v[2] for v in partials)
  assert o['extended_contradictions']==len(extended)
  assert po['records']==len(partials)
  assert po['rank_sum']==sum(v[1] for v in partials)
  assert po['assignments']==sum(v[3] for v in partials)
  assert po['inconsistent']==sum(v[2] for v in partials)


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--metal',action='store_true');args=parser.parse_args()
 if args.output.exists():raise FileExistsError(args.output)
 source_bindings={str(p):sha(p) for pattern in ('*.py','*.cpp','*.h') for p in HERE.glob(pattern)}
 binary_bindings={str(p):sha(p) for p in (HERE/'build').glob('*') if p.suffix in ('.so','.dylib')}
 receipt=read(HERE/'build/receipt.json')
 for p,h in receipt['sources'].items():
  assert sha(HERE.parent/p)==h
 for n,h in receipt['binaries'].items():assert sha(HERE/'build'/n)==h
 old_receipt=read(ORIGINAL/'build/receipt.json')
 # Bind the executed producer, descent and replay, plus every old source.
 for n,h in old_receipt['sources'].items():
  path=ORIGINAL.parent/n;assert sha(path)==h;source_bindings[str(path)]=h
 for folder in ('round17','round20','round23','round27','round31','round32','round34','round37','round44'):
  for p in (ORIGINAL.parent/folder/'build').glob('*'):
   if p.suffix in ('.so','.dylib'):binary_bindings[str(p)]=sha(p)
 reference_path=ORIGINAL/'evidence/physical-m4-correctness.json.gz';reference=read(reference_path)
 audit=reference['independent_audit']
 assert reference['status']==audit['status']=='PASS' and audit['input_sha256']==reference['full_correctness_sha256']
 references={str(p):sha(p) for p in (reference_path,HERE/'build/receipt.json',ORIGINAL/'build/receipt.json')}
 corpus_path=ORIGINAL.parent/'round42/fixtures/controls.json.gz';manifest=read(corpus_path.parent/'manifest.json');assert sha(corpus_path)==manifest['sha256']
 inputs_path=ORIGINAL.parent/'round40/fixtures/inputs.json.gz';inputs=read(inputs_path);cases=read(corpus_path)
 assert len(cases)==6001 and len(inputs)==18 and sha(inputs_path)==audit['fixture_sha256']
 references.update({str(corpus_path):sha(corpus_path),str(inputs_path):sha(inputs_path)})
 ref_controls={(r['case'],r['backend'],r['sanitizer'],r['partial_enabled']):r for r in reference['controls']}
 ref_queries={(r['name'],r['backend'],r['sanitizer'],r['partial_enabled']):r['result'] for r in reference['queries']}
 audit_queries={(r['name'],r['backend'],r['sanitizer'],r['partial_enabled']):r for r in audit['records']}
 modes=[('cpu',False),('cpu',True)];metal={'requested':args.metal,'status':'NOT_REQUESTED','device':None}
 if args.metal:
  try:
   with producer.Producer(2,3,3,backend='metal') as p:metal.update(status='AVAILABLE',device=p.device)
  except ValueError as err:
   if str(err)!='requested Metal device unavailable':raise
   metal.update(status='UNAVAILABLE',detail=str(err))
  else:modes.append(('metal',False))
 report={'schema':'independent-grouped-identity-checker-validation/1','status':'RUNNING','architecture':platform.machine(),'platform':platform.platform(),'metal':metal,'sources':source_bindings,'binaries':binary_bindings,'references':references,'controls':[],'queries':[],'proofs':{},'timing_eligible':False,'candidate_id':None,'online_speedup':None}
 def bindings():
  for mapping in (source_bindings,binary_bindings,references):
   for p,h in mapping.items():assert sha(Path(p))==h,p
 bindings()
 truths={name:truth(x+y,terms) for name,x,y,e,terms,mod,kind in cases}
 with gzip.open(args.output.with_suffix(args.output.suffix+'.jsonl.gz'),'xt',compresslevel=1) as journal:
  def retain(section,row):
   report[section].append(row);journal.write(json.dumps({'section':section,**row},separators=(',',':'))+'\n');journal.flush()
  for backend,sanitizer in modes:
   with ExitStack() as stack:
    contexts={}
    for i,(name,x,y,e,terms,modulus,kind) in enumerate(cases):
     shape=x,y,e,modulus
     if shape not in contexts:
      p=stack.enter_context(producer.Producer(x,y,e,backend=backend,sanitizer=sanitizer))
      if modulus is not None:p.configure_normalization(modulus)
      c=stack.enter_context(candidate.Checker(x,y,e,sanitizer=sanitizer));old=stack.enter_context(accepted_checker.Checker(x,y,e,sanitizer=sanitizer));contexts[shape]=p,c,old
     p,c,old=contexts[shape];packed=producer.Packed(x+y,e,terms)
     for partial in (False,True):
      p.configure_partial(partial);ref=ref_controls[name,backend,sanitizer,partial]
      try:answer=p.produce(packed)
      except producer.Inconclusive as error:
       assert len(truths[name])>256 and ref['status']=='expected-inconclusive' and 'complete roots exceed 256' in str(error)
       for symmetry in (False,True):
        for transform,identity in CONTROL_VARIANTS:retain('controls',{'case':name,'shape':[x,y,e],'backend':backend,'sanitizer':sanitizer,'partial_enabled':partial,'symmetry_enabled':symmetry,'transform_mode':transform,'identity_mode':identity,'status':'expected-inconclusive','detail':str(error),'producer':integers(error.metrics)})
       continue
      assert ref['status']=='verified' and answer['proof_sha256']==ref['proof_sha256']
      assert answer['roots']==truths[name]
      assert verify_basis(x+y,terms,answer['roots'],answer['basis'],len(answer['roots']))
      oracle=certify_roots(x,y,e,tuple(tuple(t) for t in terms),answer['proof_bytes'],sys.byteorder)
      baseline=old.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
      assert integers(baseline['stats'])==ref['checker'] and integers(baseline['partial_stats'])==ref['checker_partial']
      for symmetry in (False,True):
       c.configure_symmetry(symmetry)
       for transform,identity in CONTROL_VARIANTS:
        c.configure_transform(transform);c.configure_identity(identity);check=c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes']);reconcile(check,baseline,x,y,e,oracle)
        retain('controls',{'case':name,'shape':[x,y,e],'backend':backend,'sanitizer':sanitizer,'partial_enabled':partial,'symmetry_enabled':symmetry,'transform_mode':transform,'identity_mode':identity,'status':'verified','proof_sha256':answer['proof_sha256'],'roots':answer['roots'],'checker':integers(check['stats']),'checker_partial':integers(check['partial_stats']),'checker_symmetry':integers(check['symmetry_check_stats']),'checker_transform':integers(check['transform_check_stats']),'checker_identity':integers(check['identity_check_stats'])})
     if (i+1)%1000==0:print('CONTROLS_PASS',backend,sanitizer,i+1,'partial on/off; symmetry on/off',flush=True)
  for backend,sanitizer in modes:
   with ExitStack() as stack:
    contexts={}
    for item in inputs:
     shape=tuple(item[k] for k in ('n','mod','b','m','ell'))
     if shape not in contexts:
      q=stack.enter_context(NormalizedQuery(*shape,backend=backend,sanitizer=sanitizer))
      old=stack.enter_context(accepted_checker.Checker(2*shape[-1],shape[-1],shape[0],sanitizer=sanitizer))
      contexts[shape]=q,old
     q,old=contexts[shape]
     for partial in (False,True):
      q.basis.producer.configure_partial(partial);ref=ref_queries[item['name'],backend,sanitizer,partial];independent=audit_queries[item['name'],backend,sanitizer,partial]
      for symmetry in (False,True):
       q.checker.configure_symmetry(symmetry)
       for transform,identity in QUERY_VARIANTS:
        q.checker.configure_transform(transform);q.checker.configure_identity(identity);answer=q.solve(Point(**item['target']))
        assert answer['status']=='solved' and answer['verified']
        proof=answer.pop('proof_bytes');h=hashlib.sha256(proof).hexdigest()
        assert h==answer['proof_sha256']==ref['proof_sha256']==independent['proof_sha256']
        assert len(proof)==reference['proof_manifest'][h]['bytes']
        for k in ('basis_terms','assignment','basis_sha256'):assert answer[k]==ref[k]
        assert answer['basis_certificate']['solutions']==ref['basis_certificate']['solutions']==independent['roots']
        packed=producer.Packed(item['nvars'],item['n'],item['reference_anf'])
        baseline=old.certify(packed,answer['basis_certificate']['solutions'],answer['basis_terms'],proof)
        reconcile(answer['basis_certificate'],baseline,2*item['ell'],item['ell'],item['n'])
        expected_gpu=backend=='metal' and item['n']<=32;assert bool(answer['metrics']['gpu_used'])==expected_gpu
        assert answer['verifier_binary_sha256']==q.checker.binary_sha256
        report['proofs'].setdefault(h,base64.b64encode(proof).decode())
        retain('queries',{'name':item['name'],'workload_sha256':item['workload_sha256'],'backend':backend,'sanitizer':sanitizer,'partial_enabled':partial,'symmetry_enabled':symmetry,'transform_mode':transform,'identity_mode':identity,'result':answer,'original_anf_audit':independent})
        print('QUERY_PASS',item['name'],backend,sanitizer,'partial',partial,'symmetry',symmetry,'transform',transform,'identity',identity,flush=True)
 assert len(report['controls'])==6001*4*len(CONTROL_VARIANTS)*len(modes) and len(report['queries'])==18*4*len(QUERY_VARIANTS)*len(modes)
 bindings();report['status']='PASS';args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
 print('GROUPED_IDENTITY_VALIDATION_PASS',len(report['controls']),'system records;',len(report['queries']),'complete queries;',len(report['proofs']),'proofs',flush=True)

if __name__=='__main__':main()
