"""Original-ANF symmetry, malformed aliases, complete roots and bounded fallbacks."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import importlib.util
import json
from pathlib import Path
import random
import sys
import unittest

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/'round44'
from adapter import accepted_checker, producer
import independent_checker as candidate
from tagged_reference import TAG,certify_roots
from quadratic_reference import verify_basis


def integers(row):
 return {k:v for k,v in row.items() if type(v) is int}

def truth(n,terms):
 roots=[]
 for a in range(1<<n):
  value=0
  for m,c in terms:
   if a&m==m:value ^= c
  if not value:roots.append(a)
 return roots

def words(raw):
 return list((producer.U64*(len(raw)//8)).from_buffer_copy(raw))

def raw(values):
 return bytes((producer.U64*len(values))(*values))


class SymmetryTests(unittest.TestCase):
 def compare(self,x,y,e,terms,p,c,old,proof=None):
  packed=producer.Packed(x+y,e,terms)
  answer=p.produce(packed)
  proof=answer['proof_bytes'] if proof is None else proof
  new=c.certify(packed,answer['roots'],answer['basis'],proof)
  baseline=old.certify(packed,answer['roots'],answer['basis'],proof)
  self.assertTrue(new['verified'],new)
  self.assertTrue(baseline['verified'],baseline)
  expected=truth(x+y,terms)
  self.assertEqual(answer['roots'],expected)
  self.assertTrue(verify_basis(x+y,terms,expected,answer['basis'],len(expected)))
  oracle=certify_roots(x,y,e,tuple(tuple(t) for t in terms),proof,sys.byteorder)
  self.assertEqual(list(oracle[0]),expected)
  s=new['symmetry_check_stats'];n=new['stats'];o=baseline['stats'];pn=new['partial_stats'];po=baseline['partial_stats']
  for key in ('branches','contradictions','enumerated_branches','roots','standard','work','workspace_bytes','proof_bytes','transform_xors','extended_contradictions'):
   self.assertEqual(n[key],o[key],key)
  self.assertEqual(n['assignments']+s['avoided_assignments'],o['assignments'])
  self.assertEqual(pn['records']+s['partial_aliases'],po['records'])
  self.assertEqual(pn['rank_sum']+s['derived_partial_rank'],po['rank_sum'])
  self.assertEqual(pn['inconsistent']+s['derived_partial_inconsistent'],po['inconsistent'])
  self.assertEqual(pn['assignments']+s['derived_partial_assignments'],po['assignments'])
  self.assertEqual(n['multiplier_parities']+s['avoided_multiplier_parities'],o['multiplier_parities'])
  self.assertEqual(n['multiplier_words']+s['multiplier_aliases']*(y+1)*((e+63)//64),o['multiplier_words'])
  self.assertEqual(s['inferred_aliases'],s['constant_aliases']+s['multiplier_aliases']+s['partial_aliases']+s['enumerated_aliases'])
  if not s['enabled']:
   self.assertEqual(integers(n),integers(o))
   self.assertEqual(integers(pn),integers(po))
  return answer,new

 def test_all_four_branch_kinds_and_diagonals(self):
  systems=[(3,[(0,1)],'constant_aliases'),(2,[(4,1),(8,2),(12,4),(0,4)],'multiplier_aliases'),(3,[(4,1),(24,2),(0,2)],'partial_aliases'),(3,[(4,1),(8,2),(16,4),(0,6)],'enumerated_aliases')]
  for sanitizer in (False,True):
   for y,terms,key in systems:
    with self.subTest(y=y,kind=key,sanitizer=sanitizer),producer.Producer(2,y,3,sanitizer=sanitizer) as p,candidate.Checker(2,y,3,sanitizer=sanitizer) as c,accepted_checker.Checker(2,y,3,sanitizer=sanitizer) as old:
     _,a=self.compare(2,y,3,terms,p,c,old)
     self.assertEqual(a['symmetry_check_stats'][key],1)
     self.assertEqual(a['symmetry_check_stats']['representatives'],1)
     self.assertEqual(a['symmetry_check_stats']['enabled'],1)

 def test_wide_equations_residual_shapes_and_root_orbits(self):
  for sanitizer in (False,True):
   for y in (3,7,10):
    rank=max(1,y-3)
    for e in (max(3,rank+1),31,32,63,64,65,127,128):
     terms=[(1<<(2+j),1<<j) for j in range(rank)]+[(((1<<(y-2))|(1<<(y-1)))<<2,1<<(e-1)),(0,1<<(e-1))]
     with self.subTest(y=y,e=e,sanitizer=sanitizer),producer.Producer(2,y,e,sanitizer=sanitizer) as p,candidate.Checker(2,y,e,sanitizer=sanitizer) as c,accepted_checker.Checker(2,y,e,sanitizer=sanitizer) as old:
      answer,a=self.compare(2,y,e,terms,p,c,old)
      self.assertEqual(a['symmetry_check_stats']['partial_aliases'],1)
      reduced=[r for r in answer['roots'] if (r&3)!=2]
      self.assertEqual(c.certify(producer.Packed(2+y,e,terms),reduced,answer['basis'],answer['proof_bytes'])['code'],3)

 def test_fresh_guard_and_ablation_on_reused_context(self):
  terms=[(4,1),(24,2),(0,2)]
  for sanitizer in (False,True):
   with producer.Producer(2,3,3,sanitizer=sanitizer) as p,candidate.Checker(2,3,3,sanitizer=sanitizer) as c,accepted_checker.Checker(2,3,3,sanitizer=sanitizer) as old:
    for changed in (terms,terms+[(1,1)],terms,terms+[(2,4)],terms):
     _,a=self.compare(2,3,3,changed,p,c,old)
     self.assertEqual(a['symmetry_check_stats']['enabled'],int(changed==terms))
     self.assertEqual(a['symmetry_check_stats']['asymmetric_fallback'],int(changed!=terms))
    c.configure_symmetry(False)
    _,a=self.compare(2,3,3,terms,p,c,old)
    self.assertEqual(a['symmetry_check_stats']['work'],0)
    c.configure_symmetry(True)
    _,a=self.compare(2,3,3,terms,p,c,old)
    self.assertEqual(a['symmetry_check_stats']['partial_aliases'],1)
  with producer.Producer(3,3,3) as p,candidate.Checker(3,3,3) as c,accepted_checker.Checker(3,3,3) as old:
   _,a=self.compare(3,3,3,[(8,1),(48,2),(0,2)],p,c,old)
   self.assertEqual(a['symmetry_check_stats']['shape_fallback'],1)

 def test_valid_different_missing_and_degenerate_certificates(self):
  terms=[(4,1),(24,2),(0,2)]
  for sanitizer in (False,True):
   with producer.Producer(2,3,3,sanitizer=sanitizer) as p,candidate.Checker(2,3,3,sanitizer=sanitizer) as c,accepted_checker.Checker(2,3,3,sanitizer=sanitizer) as old:
    answer=p.produce(producer.Packed(5,3,terms));original=words(answer['proof_bytes'])
    for variant in ('zero-all','dependent-all','reverse-all','zero-alias','dependent-alias','reverse-alias','missing-representative','missing-alias','missing-all'):
     w=original[:]
     if variant=='missing-representative':del w[9:14]
     elif variant=='missing-alias':del w[14:19]
     elif variant=='missing-all':w=w[:4]
     else:
      for offset in (range(4,len(w),5) if variant.endswith('all') else (14,)):
       if variant.startswith('zero'):w[offset+1:offset+5]=[0]*4
       elif variant.startswith('dependent'):w[offset+2]=w[offset+1]
       else:w[offset+1:offset+5]=reversed(w[offset+1:offset+5])
     with self.subTest(variant=variant,sanitizer=sanitizer):
      _,a=self.compare(2,3,3,terms,p,c,old,raw(w))
      if variant in ('dependent-alias','reverse-alias','zero-alias','missing-alias','missing-representative'):
       self.assertEqual(a['symmetry_check_stats']['proof_mismatches'],1)
       self.assertEqual(a['symmetry_check_stats']['inferred_aliases'],0)
  with producer.Producer(2,3,3,copy_budget_test=True) as p,candidate.Checker(2,3,3) as c,accepted_checker.Checker(2,3,3) as old:
   _,a=self.compare(2,3,3,terms,p,c,old)
   self.assertEqual(a['symmetry_check_stats']['proof_mismatches'],1)

 def test_invalid_alias_and_equal_invalid_witnesses_rejected(self):
  terms=[(4,1),(24,2),(0,2)];packed=producer.Packed(5,3,terms)
  for sanitizer in (False,True):
   with producer.Producer(2,3,3,sanitizer=sanitizer) as p,candidate.Checker(2,3,3,sanitizer=sanitizer) as c:
    a=p.produce(packed);original=words(a['proof_bytes'])
    for kind in ('alias-nonlinear','both-nonlinear','wrong-kind','both-wrong-kind'):
     w=original[:]
     if 'nonlinear' in kind:
      w[15]=2
      if kind.startswith('both'):w[10]=2
     else:
      w[14]&=~TAG
      if kind.startswith('both'):w[9]&=~TAG
     self.assertEqual(c.certify(packed,a['roots'],a['basis'],raw(w))['code'],9,kind)
    for kind in ('padding','duplicate','reorder','overlap','extent','unknown-tag'):
     w=original[:]
     if kind=='padding':w[15]|=8
     elif kind=='duplicate':w[14]=w[9]
     elif kind=='reorder':w[9:14],w[14:19]=w[14:19],w[9:14]
     elif kind=='overlap':w[2]=1
     elif kind=='extent':w.pop()
     else:w[14]|=1<<62
     with self.subTest(kind=kind),self.assertRaises(ValueError):c.certify(packed,a['roots'],a['basis'],raw(w))
    self.assertEqual(c.certify(packed,a['roots'],[],a['proof_bytes'])['code'],4)
    self.assertFalse(c.certify(producer.Packed(5,3,terms[:-1]),a['roots'],a['basis'],a['proof_bytes'])['verified'])

 def test_external_full_rank_inconsistent_and_rank_zero(self):
  for sanitizer in (False,True):
   for e,positions in ((4,(0,1,2,3)),(128,(0,63,64,127))):
    for inconsistent in (False,True):
     witnesses=[1<<b for b in positions]
     terms=[(4<<i,witnesses[i]) for i in range(3)]+[(0,witnesses[0]|witnesses[2]|(witnesses[3] if inconsistent else 0))]
     if not inconsistent:witnesses[3]=0
     limbs=(e+63)//64;w=[0]*(4*limbs)
     for branch in range(4):
      w.append(TAG|branch)
      for u in witnesses:w.extend((u>>(64*l))&((1<<64)-1) for l in range(limbs))
     with producer.Producer(2,3,e,sanitizer=sanitizer) as p,candidate.Checker(2,3,e,sanitizer=sanitizer) as c,accepted_checker.Checker(2,3,e,sanitizer=sanitizer) as old:
      _,a=self.compare(2,3,e,terms,p,c,old,raw(w))
      self.assertEqual(a['partial_stats']['rank_sum'],9)
      self.assertEqual(a['symmetry_check_stats']['derived_partial_rank'],3)
      self.assertEqual(a['partial_stats']['inconsistent'],3*inconsistent)
      self.assertEqual(a['symmetry_check_stats']['derived_partial_inconsistent'],int(inconsistent))

 def test_work_and_workspace_fallback_including_partial_setup(self):
  terms=[(16,1),(96,2),(0,2)]
  with producer.Producer(4,3,3) as p,accepted_checker.Checker(4,3,3) as old:
   for flag,field in (('symmetry_budget_test','budget_fallback'),('symmetry_workspace_test','workspace_fallback'),('symmetry_late_budget_test','budget_fallback')):
    with candidate.Checker(4,3,3,**{flag:True}) as c:
     _,a=self.compare(4,3,3,terms,p,c,old)
     s=a['symmetry_check_stats'];self.assertEqual(s[field],1);self.assertEqual(s['enabled'],0);self.assertEqual(s['inferred_aliases'],0)
     if flag=='symmetry_late_budget_test':self.assertGreaterEqual(s['proof_pairs'],2);self.assertEqual(s['work'],60)
     # A second query must not consume reuse flags left by aborted setup.
     self.compare(4,3,3,terms,p,c,old)
  packed=producer.Packed(5,3,[(4,1),(24,2),(0,2)])
  with producer.Producer(2,3,3) as p:
   answer=p.produce(packed)
   for flag in ('budget_test','partial_budget_test'):
    with candidate.Checker(2,3,3,**{flag:True}) as c:
     a=c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
     self.assertEqual(a['code'],5);self.assertIsNone(a['root_count']);self.assertFalse(a['verified'])
  with candidate.Checker(8,1,1) as c:
   a=c.certify(producer.Packed(9,1,[]),[],[],bytes(256*8))
   self.assertEqual(a['code'],5);self.assertIsNone(a['root_count'])

 def test_duplicate_cancelled_unsorted_and_both_mask_widths(self):
  base=[(4,1),(24,2),(0,2)]
  variants=[base,base+[(1,4),(1,4)],list(reversed(base))+[(28,0)],[(0,2),(4,3),(24,2),(4,2)]]
  for sanitizer in (False,True):
   with producer.Producer(2,3,3,sanitizer=sanitizer) as p,candidate.Checker(2,3,3,sanitizer=sanitizer) as c,accepted_checker.Checker(2,3,3,sanitizer=sanitizer) as old:
    answer=p.produce(producer.Packed(5,3,base))
    for terms in variants:
     for width in (32,64):
      packed=producer.Packed(5,3,terms)
      if width==32:packed.masks=(producer.U32*len(terms))(*(m for m,_ in terms))
      a=c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
      b=old.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
      self.assertTrue(a['verified']);self.assertTrue(b['verified'])
      self.assertEqual(a['symmetry_check_stats']['enabled'],1)
      self.assertEqual(a['symmetry_check_stats']['partial_aliases'],1)
      self.assertEqual(truth(5,terms),answer['roots'])

 def test_constant_and_multiplier_alias_mutations(self):
  for sanitizer in (False,True):
   for y,terms,kind in ((2,[(0,1)],'constant'),(2,[(4,1),(8,2),(12,4),(0,4)],'multiplier')):
    with producer.Producer(2,y,128,sanitizer=sanitizer) as p,candidate.Checker(2,y,128,sanitizer=sanitizer) as c,accepted_checker.Checker(2,y,128,sanitizer=sanitizer) as old:
     packed=producer.Packed(2+y,128,terms);a=p.produce(packed);original=words(a['proof_bytes'])
     for both in (False,True):
      w=original[:]
      if kind=='constant':
       w[4:6]=[0,1<<63]
       if both:w[2:4]=[0,1<<63]
      else:
       # x=2 and x=1 tail payloads, leaving their ordered headers intact.
       w[23:29]=[0]*6
       if both:w[16:22]=[0]*6
      result=c.certify(packed,a['roots'],a['basis'],raw(w))
      self.assertEqual(result['code'],9,(kind,both))
     if kind=='multiplier':
      # Add an unused equation to one multiplier: a different valid proof
      # must be checked independently, rather than rejected or skipped.
      w=original[:];w[24]^=1<<63
      _,result=self.compare(2,y,128,terms,p,c,old,raw(w))
      self.assertEqual(result['symmetry_check_stats']['proof_mismatches'],1)

 def test_configuration_lifecycle_and_concurrent_reuse(self):
  terms=[(4,1),(24,2),(0,2)];packed=producer.Packed(5,3,terms)
  with producer.Producer(2,3,3) as p,candidate.Checker(2,3,3) as c:
   a=p.produce(packed)
   for bad in (0,1,None,'yes'):
    with self.assertRaises(ValueError):c.configure_symmetry(bad)
    with self.assertRaises(ValueError):candidate.Checker(2,3,3,symmetry=bad)
   self.assertEqual(c.lib.check_symmetry_configure(c._handle,2),-1)
   expected=c.certify(packed,a['roots'],a['basis'],a['proof_bytes'])
   def check(_):return c.certify(packed,a['roots'],a['basis'],a['proof_bytes'])
   with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,range(16)))
   for result in results:
    self.assertTrue(result['verified']);self.assertEqual(integers(result['symmetry_check_stats']),integers(expected['symmetry_check_stats']))
  with self.assertRaises(RuntimeError):c.configure_symmetry(True)
  with self.assertRaises(RuntimeError):c.certify(packed,a['roots'],a['basis'],a['proof_bytes'])

 def test_seeded_symmetric_and_asymmetric_systems(self):
  rng=random.Random(2026100145)
  for sanitizer in (False,True):
   for x in (2,4):
    with producer.Producer(x,3,5,sanitizer=sanitizer) as p,candidate.Checker(x,3,5,sanitizer=sanitizer) as c,accepted_checker.Checker(x,3,5,sanitizer=sanitizer) as old:
     for index in range(100):
      d={};half=x//2
      for _ in range(12):
       left=rng.randrange(1<<x);right=rng.choice([m for m in range(8) if m.bit_count()<=2]);coef=rng.randrange(1,32)
       swapped=((left&((1<<half)-1))<<half)|(left>>half)
       for a in {left,swapped}:d[a|(right<<x)]=d.get(a|(right<<x),0)^coef
      if index%2:d[1]=d.get(1,0)^1
      terms=sorted((m,v) for m,v in d.items() if v)
      with self.subTest(x=x,index=index,sanitizer=sanitizer):self.compare(x,3,5,terms,p,c,old)

if __name__=='__main__':unittest.main(verbosity=2)
