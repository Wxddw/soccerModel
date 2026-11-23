import copy
import pytest
from benchmark_joint_tail_shadow_r636 import run
from test_joint_tail_calibration_shadow_r636 import history, Q

def make_payload():
    held=[]
    for i in range(10):
        r={'match_id':f'hold-{i}','source_id':'live-licensed-synthetic',
           'observed_at':'2026-02-03T15:00:00+08:00',
           'cutoff':'2026-02-03T16:00:00+08:00',
           'kickoff':'2026-02-03T19:00:00+08:00',
           'result_observed_at':'2026-02-03T22:00:00+08:00',
           'score_matrix':copy.deepcopy(Q),
           'actual_score':('2:2' if i%2 else '2:0'),
           'official_jc_line':-1,'authorized_for_analysis':True}
        held.append(r)
    return {'authorized_for_analysis':True,'calibration_id':'synthetic-early-only',
            'development':history(),'holdout':held}

def test_chronological_paired_benchmark_is_only_research():
    x=make_payload();old=copy.deepcopy(x)
    out=run(x)
    assert x==old and out['development_n']==80 and out['holdout_n']==10
    assert out['upstream_outcome_locked'] and out['certified_improvement'] is False
    assert out['formal_grant'] is None
    for k in ('score_ll','score_brier','goal_ll','goal_brier','jc_ll','jc_brier'):
        assert len(out['paired_differences'][k]['paired_bootstrap95'])==2

def test_benchmark_training_leakage_and_duplicate_blocks():
    x=make_payload();x['development'][0]['result_observed_at']='2026-02-04T00:00:00+08:00'
    with pytest.raises(ValueError):run(x)
    x=make_payload();x['holdout'][0]['match_id']=x['development'][0]['match_id']
    with pytest.raises(ValueError,match='duplicate'):run(x)

def test_no_unlicensed_holdout():
    x=make_payload();x['holdout'][0]['authorized_for_analysis']=False
    with pytest.raises(ValueError):run(x)
