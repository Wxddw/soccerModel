import copy
import pytest
from benchmark_htft_transition_v2_r636 import run

def rec(i,period):
    # made-up authorized synthetic example, NOT real match records
    day=(i%20)+1
    return {'match_id':f'{period}-{i}','kickoff':f'2026-{"10" if period=="dev" else "11"}-{day:02d}T12:00:00+08:00',
            'source_observed_at':f'2026-{"10" if period=="dev" else "11"}-{day:02d}T09:00:00+08:00',
            'cutoff':f'2026-{"10" if period=="dev" else "11"}-{day:02d}T10:00:00+08:00',
            'score_matrix':[{'score':'0:0','probability':.2},{'score':'1:0','probability':.4},{'score':'0:1','probability':.4}],
            'full_time_score':'1:0','half_time_score':'0:0',
            'result_observed_at':f'2026-{"10" if period=="dev" else "11"}-{day:02d}T15:00:00+08:00'}

def test_benchmark_is_only_research_and_paired():
    data={'authorized_for_analysis':True,'development':[rec(i,'dev') for i in range(8)],'holdout':[rec(i,'test') for i in range(4)]}
    original=copy.deepcopy(data)
    v=run(data)
    assert data==original
    assert v['n_development']==8 and v['n_holdout']==4
    assert v['formal_grant'] is None
    assert v['candidate']['log_loss'] < v['baseline']['log_loss']

def test_benchmark_strictly_disallows_cross_split_leakage():
    data={'authorized_for_analysis':True,'development':[rec(0,'dev')],'holdout':[rec(0,'test')]}
    data['holdout'][0]['source_observed_at']='2026-09-01T01:00:00+08:00'
    with pytest.raises(ValueError):run(data)
    data['holdout'][0]['source_observed_at']='2026-11-01T09:00:00+08:00'
    data['holdout'][0]['match_id']=data['development'][0]['match_id']
    with pytest.raises(ValueError,match='duplicate'):run(data)
