"""Audit the frozen kernel screen and retain every primary comparison."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    folder = HERE/'kernel-timing-v1'
    output = folder/'analysis.json'
    if output.exists():
        raise FileExistsError(output)
    report = json.loads((folder/'summary.json').read_text())
    assert report['status'] == 'RECORDED' and report['source_unchanged']
    for p,h in report['bindings'].items():
        assert sha(p) == h, p
    plan = json.loads((HERE/'kernel-plan.json').read_text())
    assert plan == report['plan']
    journal = [json.loads(line) for line in (folder/'journal.jsonl').read_text().splitlines()]
    raw = {(r['trial'],r['pair'],r['method']):r for r in journal if r['event']=='kernel'}
    assert len(raw) == sum(r['event']=='kernel' for r in journal)
    primary = plan['primary']
    rng = random.Random(202610014605)
    trials, rejected = [], 0
    for trial in report['trials']:
        record = {k:trial[k] for k in ('name','k','word_bits','repetition','status','qualified')}
        trials.append(record)
        if trial['status'] == 'NOT_RUN_ADMISSION_EXHAUSTED':
            assert rejected >= plan['admission']['max_rejected_admissions']
            assert not trial['rows'] and not trial['admission'] and not trial['qualified']
            continue
        assert rejected < plan['admission']['max_rejected_admissions']
        if trial['status'] == 'NOT_ADMITTED':
            rejected += 1
            assert trial['admission'][-1]['elapsed_seconds'] >= plan['admission']['max_wait_seconds']
            assert all(s['load'][0]>report['threshold'] for s in trial['admission'])
            assert not trial['rows'] and not trial['qualified']
            continue
        assert trial['status'] == 'RECORDED'
        assert trial == json.loads((folder/(trial['name']+'.json')).read_text())
        assert trial['admission'][-1]['load'][0] <= report['threshold']
        maximum = max(trial['admission'][-1]['load'][0],trial['load_end'][0])
        grouped = {}
        for row in trial['rows']:
            assert row['code'] == 0 and row['verified'] and row['elapsed_ns']>0
            assert raw[trial['name'],row['pair'],row['method']] == {'trial':trial['name'],'event':'kernel',**row}
            assert sorted(row['order']) == list(range(len(plan['methods'])))
            assert row['counts'][2] == 0 # Guard deliberately excluded from this conditional kernel.
            assert row['counts'][3] == plan['methods'].index(row['method'])
            maximum = max(maximum,row['load'][0],row['load_end'][0])
            grouped.setdefault(row['pair'],{})[row['method']] = row
        assert sorted(grouped) == list(range(-plan['warmup_pairs'],plan['measured_pairs']))
        assert all(set(p)==set(plan['methods']) for p in grouped.values())
        assert maximum == trial['maximum_sampled_load']
        assert trial['qualified'] == (maximum <= report['threshold'])
        rows = [grouped[i] for i in range(plan['measured_pairs'])]
        record['median_us'] = {method:statistics.median(r[method]['elapsed_ns'] for r in rows)/1000 for method in plan['methods']}
        record['comparisons'] = {}
        for method in plan['methods']:
            if method == primary:
                continue
            ratios = [r[method]['elapsed_ns']/r[primary]['elapsed_ns'] for r in rows]
            boot = sorted(statistics.median(rng.choices(ratios,k=len(ratios))) for _ in range(10000))
            record['comparisons'][method] = {'paired_median_ratio':statistics.median(ratios),
                'lower95':boot[250],'upper95':boot[9750], 'ratios':ratios}
        record['positive_against_every_other_method'] = trial['qualified'] and all(c['lower95']>1 for c in record['comparisons'].values())
    repeated, baseline_wins = [], []
    for width in plan['word_bits']:
        for k in plan['k']:
            pair = [t for t in trials if t['k']==k and t['word_bits']==width]
            assert len(pair)==2
            if all(t.get('positive_against_every_other_method',False) for t in pair):
                repeated.append({'k':k,'word_bits':width})
            if all(t['qualified'] and t['comparisons']['accepted-full']['lower95']>1 for t in pair):
                baseline_wins.append({'k':k,'word_bits':width})
    result = {'schema':'conditional-symmetric-transform-kernel-analysis/1','audit_status':'PASS',
              'report_sha256':sha(folder/'summary.json'),'journal_sha256':sha(folder/'journal.jsonl'),
              'analysis_sha256':sha(Path(__file__)),'primary':primary,'trials':trials,
              'status_counts':dict(Counter(t['status'] for t in trials)),
              'verified_calls':len(raw),'qualified_trials':sum(t['qualified'] for t in trials),
              'repeated_primary_win_against_all':repeated,
              'repeated_primary_win_against_accepted_full':baseline_wins,
              'scope':plan['scope'],'dispatch_changed':False,'candidate_id':None,'online_speedup':None}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},indent=2))
    for t in trials:
        if 'median_us' in t:
            print(t['name'],'qualified',t['qualified'],'median_us',t['median_us'],flush=True)


if __name__ == '__main__':
    main()
