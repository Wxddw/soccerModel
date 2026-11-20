import copy
import pytest
from benchmark_htft_segment_r636 import run
from test_htft_segment_hazard_r636 import history

def wrapped(i,kind):
    r=history(i,kind)
    if kind=='hold':
        r['score_matrix']=[{'score':'0:0','probability':.15},
                          {'score':'1:0','probability':.50},
                          {'score':'0:1','probability':.35}]
    return r

def test_synthetic_development_holdout_benchmark():
    data={'authorized_for_analysis':True,'development':[wrapped(i,'dev') for i in range(8)],
          'holdout':[wrapped(i,'hold') for i in range(5)]}
    frozen=copy.deepcopy(data)
    out=run(data)
    assert data==frozen
    assert out['formal_grant'] is None
    assert out['n_development']==8 and out['n_holdout']==5
    assert out['baseline_neutral_six_period']['n']==5
    assert len(out['log_loss_delta_ci']['bootstrap_95pct'])==2

def test_holdout_result_not_used_in_training():
    data={'authorized_for_analysis':True,'development':[wrapped(0,'dev')],
          'holdout':[wrapped(0,'hold')]}
    data['development'][0]['result_observed_at']='2026-11-02T00:00:00+08:00'
    with pytest.raises(ValueError):run(data)

def test_cross_split_duplicate_blocks():
    data={'authorized_for_analysis':True,'development':[wrapped(0,'dev')],
          'holdout':[wrapped(0,'hold')]}
    data['holdout'][0]['match_id']='dev-0'
    with pytest.raises(ValueError,match='duplicate'):run(data)
