"""Reject partial panels, budget failures, load spikes and inconsistent accounting."""
from copy import deepcopy
import unittest
from common import arm_order,arms,fixtures,plan
from analyze import summarize

def synthetic():
    config=plan();case=next(c for c in fixtures() if c['name']=='pdp-6-seed-1')
    config.update(primary_cases=[case['name']],primary_trials=1,primary_pairs=2,bootstrap_samples=100)
    task={'case':case['name'],'trial':0,'pairs':2,'primary':True}
    trial={**task,'admission_load':[0,0,0],'admitted':True,'complete':True,'qualified':True,'pairs':[]}
    rows=[]
    for repetition in range(3):
        order=arm_order(case,0,repetition);pair={'repetition':repetition,'warmup':repetition==0,'order':order,'rows':[]}
        for arm in order:
            wall=100 if arm=='native' else 400
            pair['rows'].append(len(rows))
            rows.append({'case':case['name'],'trial':0,'repetition':repetition,'warmup':repetition==0,'arm':arm,
                         'load_before':[0,0,0],'load_after':[0,0,0],'matches_preflight':True,
                         'measurement':{'wall_ns':wall,'parent_cpu_ns':wall,'phases':{'descent_ns':0,'algebra_and_certificate_ns':wall,'extraction_and_curve_ns':0,'reference_replay_ns':0},'result':{'status':'solved','verified':True}}})
        trial['pairs'].append(pair)
    report={'schema':'sparse-f4-complete-query-panel/1','status':'RECORDED','plan':config,'candidate_id':None,'online_speedup':None,
            'rows':len(rows),'host':{'logical_cpus':1,'load_threshold':1},'trials':[trial],'schedule':[task],
            'unrun':[],'source_bindings_unchanged':True,'rejected_admissions':0}
    return report,rows,config,{case['name']:case}

class PanelTests(unittest.TestCase):
    def test_synthetic_complete_panel_and_warmups(self):
        args=synthetic();args[1][0]['measurement']['wall_ns']=10**12;args[1][0]['measurement']['phases']={'descent_ns':0,'algebra_and_certificate_ns':10**12,'extraction_and_curve_ns':0,'reference_replay_ns':0}
        result=summarize(*args)
        self.assertTrue(result['primary_acceptance']);self.assertTrue(result['two_times_target_met'])
        self.assertEqual(result['trials'][0]['comparator_over_primary']['baseline']['median_ratio'],4)
    def test_budget_failures_have_no_speedup_denominator(self):
        args=synthetic()
        for row in args[1]:
            if row['arm']=='baseline':row['measurement']['result'].update(status='inconclusive',verified=False)
        result=summarize(*args)
        self.assertFalse(result['primary_acceptance']);self.assertIsNone(result['trials'][0]['comparator_over_primary']['baseline'])
    def test_load_spike_cannot_be_claimed_qualified(self):
        args=synthetic();args[1][-1]['load_after'][0]=2
        with self.assertRaises(AssertionError):summarize(*args)
        args[0]['trials'][0]['qualified']=False
        self.assertFalse(summarize(*args)['primary_acceptance'])
    def test_missing_trial_or_altered_phase_sum_rejected(self):
        args=synthetic();args[0]['trials']=[]
        with self.assertRaises(AssertionError):summarize(*args)
        args=synthetic();args[1][0]['measurement']['phases']['algebra_and_certificate_ns']+=1
        with self.assertRaises(AssertionError):summarize(*args)
    def test_duplicate_or_reordered_records_rejected(self):
        args=synthetic();args[0]['trials'][0]['pairs'][1]['rows'][0]=0
        with self.assertRaises(AssertionError):summarize(*args)
        args=synthetic();args[0]['trials'][0]['pairs'][0]['order'].reverse()
        with self.assertRaises(AssertionError):summarize(*args)
    def test_zero_admission_and_interrupted_pairs_remain_nonwins(self):
        report,rows,config,cases=synthetic()
        trial=report['trials'][0];trial.update(admitted=False,admission_load=[2,2,2],complete=False,qualified=False,pairs=[])
        report.update(rows=0,rejected_admissions=1)
        result=summarize(report,[],config,cases);self.assertFalse(result['primary_acceptance']);self.assertEqual(result['queries'],0)
        report,rows,config,cases=synthetic();trial=report['trials'][0]
        trial['pairs']=trial['pairs'][:1];trial['pairs'][0]['rows']=trial['pairs'][0]['rows'][:1]
        trial.update(complete=False,qualified=False);report.update(status='INTERRUPTED',rows=1)
        result=summarize(report,rows[:1],config,cases);self.assertFalse(result['primary_acceptance'])
    def test_missing_or_incomplete_phase_costs_rejected(self):
        args=synthetic();args[1][0]['measurement']['phases']=None
        with self.assertRaises(AssertionError):summarize(*args)
        args=synthetic();del args[1][0]['measurement']['phases']['reference_replay_ns']
        with self.assertRaises(AssertionError):summarize(*args)
        args=synthetic();args[1][0]['measurement']['parent_cpu_ns']=-1
        with self.assertRaises(AssertionError):summarize(*args)

    def test_unchanged_sources_required_for_acceptance(self):
        args=synthetic();args[0]['source_bindings_unchanged']=False
        self.assertFalse(summarize(*args)['primary_acceptance'])

if __name__=='__main__':unittest.main()
