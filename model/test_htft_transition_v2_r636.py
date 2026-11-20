import copy
import pytest
from htft_transition_v2_r636 import predict,fit_logits,evaluate,PATHS

C='2026-11-19T16:00:00+08:00'
K='2026-11-20T09:00:00+08:00'
O='2026-11-19T15:59:00+08:00'
def run(rows,**kw):
    return predict(rows, fraction_home=.44,fraction_away=.40,source_id='history-corpus',
                   observed_at=O,cutoff=C,kickoff=K,**kw)

def test_sum_and_fulltime_frozen_and_immutability():
    grid=[{'score':'0:0','probability':.1},{'score':'1:0','probability':.2},
          {'score':'2:1','probability':.4},{'score':'1:2','probability':.3}]
    original=copy.deepcopy(grid)
    baseline=run(grid)
    logits={k:0. for k in PATHS};logits['平胜']=1.5;logits['平负']=-1
    modified=run(grid,transition_logits=logits,
                 latest_training_kickoff='2026-11-18T20:00:00+08:00',
                 latest_training_result_observed_at='2026-11-18T23:00:00+08:00')
    assert original==grid
    assert abs(sum(modified['probabilities'].values())-1)<1e-12
    assert sum(modified['half_time_wdl'].values())==pytest.approx(1.)
    assert modified['full_time_wdl']==pytest.approx(baseline['full_time_wdl'],abs=1e-12)
    assert modified['probabilities']['平胜'] > baseline['probabilities']['平胜']
    assert modified['research_only'] and modified['formal_grant'] is None
    assert len(modified['top3'])==3

def test_0_0_is_halftime_draw_and_fulltime_draw():
    p=run([{'score':'0:0','probability':1}]);assert p['probabilities']['平平']==pytest.approx(1)

def test_one_nil_conditional_split():
    p=run([{'score':'1:0','probability':1}]);assert p['probabilities']['胜胜']==pytest.approx(.44)
    assert p['probabilities']['平胜']==pytest.approx(.56)

def test_invalid_matrix_and_timing_fail_closed():
    with pytest.raises(ValueError,match='mass'):
        run([{'score':'1:0','probability':.8}])
    with pytest.raises(ValueError):
        run([{'score':'1:0','probability':.6},{'score':'1:0','probability':.4}])
    with pytest.raises(ValueError):
        predict([{'score':'1:0','probability':1}],fraction_home=.44,fraction_away=.40,
                source_id='id',observed_at=K,cutoff=C,kickoff=K)
    with pytest.raises(ValueError):
        run([{'score':'1:0','probability':1}],transition_logits={k:0 for k in PATHS})
    with pytest.raises(ValueError):
        run([{'score':'1:0','probability':1}],transition_logits={k:0 for k in PATHS},
            latest_training_kickoff=K,latest_training_result_observed_at=K)
    with pytest.raises(ValueError):
        run([{'score':'1:0','probability':1}],transition_logits={k:0 for k in PATHS if k!='胜负'},
            latest_training_kickoff='2026-11-18T10:00:00+08:00',
            latest_training_result_observed_at='2026-11-18T12:00:00+08:00')

def test_train_development_only_and_scoring():
    h=[{'match_id':str(i),'kickoff':f'2026-11-{i+1:02d}T12:00:00+08:00',
       'full_time_score':'1:0','half_time_score':'0:0',
       'result_observed_at':f'2026-11-{i+1:02d}T15:00:00+08:00'} for i in range(6)]
    fitted=fit_logits(h,fraction_home=.44,fraction_away=.40,asof_cutoff=O)
    assert fitted['transition_logits']['平胜']>fitted['transition_logits']['胜胜']
    p=run([{'score':'1:0','probability':1}],transition_logits=fitted['transition_logits'],
          latest_training_kickoff=fitted['latest_training_kickoff'],
          latest_training_result_observed_at=fitted['latest_training_result_observed_at'])
    s=evaluate(p,full_time_score='1:0',half_time_score='0:0')
    assert s['actual']=='平胜' and s['top3_hit']
    h[0]['kickoff']=K
    with pytest.raises(ValueError,match='future'):
        fit_logits(h,fraction_home=.44,fraction_away=.4,asof_cutoff=O)

def test_reject_post_match_fields_in_prediction_grid():
    with pytest.raises(ValueError):
        run([{'score':'1:0','probability':1.,'actual_score':'1:0'}])
