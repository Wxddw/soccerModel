import copy
import math
import pytest
from htft_margin2_timeseg_shadow_r636 import (
    _phase, STATES, FACTORS, fit, predict, MIN_HISTORY
)

Q=[{'score':'3:2','probability':.5},{'score':'2:0','probability':.3},
   {'score':'0:0','probability':.2}]

def historical(n=80):
    return [{
        'match_id':f'dev{i}','source_id':f'trace{i}',
        'observed_at':'2026-01-05T12:00:00+08:00',
        'cutoff':'2026-01-05T17:00:00+08:00',
        'kickoff':'2026-01-05T18:00:00+08:00',
        'result_observed_at':'2026-01-05T21:00:00+08:00',
        'home_xg':1.4,'away_xg':1.2,
        'full_time_score':'1:0','half_time_score':'0:0',
        'goal_events':[{'minute':46,'side':'home'}],
        'authorized_for_analysis':True
    } for i in range(n)]

def calibrate():
    return fit(historical(),asof_cutoff='2026-01-06T00:00:00+08:00',
               calibration_id='synthetic-dev-only')

def pregame():
    return {'match_id':'holdout','source_id':'pregame-external',
        'observed_at':'2026-02-01T12:00:00+08:00',
        'cutoff':'2026-02-01T17:00:00+08:00',
        'kickoff':'2026-02-01T18:00:00+08:00',
        'score_matrix':copy.deepcopy(Q),'home_xg':1.5,'away_xg':1.1}

def test_fit_minimum_and_event_reconciliation():
    with pytest.raises(ValueError):fit(historical(5),asof_cutoff='2026-02-01T00:00:00+08:00',calibration_id='x')
    bad=historical();bad[0]['half_time_score']='1:0'
    with pytest.raises(ValueError,match='reconcile'):fit(bad,asof_cutoff='2026-02-01T00:00:00+08:00',calibration_id='x')
    bad=historical();bad[0]['result_observed_at']='2026-03-01T21:00:00+08:00'
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-02-01T00:00:00+08:00',calibration_id='x')

def test_eight_fitted_factors_are_bounded():
    c=calibrate()
    assert c['training_n']==80 and c['formal_grant'] is None
    assert set(c['state_factors'])==set(FACTORS)
    assert all(.7<=v<=1.3 for v in c['state_factors'].values())
    assert sum(c['home_shares'])==pytest.approx(1)
    assert sum(c['away_shares'])==pytest.approx(1)

def test_eight_state_comebacks_are_possible_and_Q_kept():
    p=pregame();frozen=copy.deepcopy(p)
    r=predict(p,calibrate())
    assert frozen==p
    assert r['formal_grant'] is None and not r['production_changed']
    assert sum(r['probabilities'].values())==pytest.approx(1)
    assert sum(r['half_time_margin_bucket_probability'].values())==pytest.approx(1)
    assert r['probability_two_goal_comeback_win']>0
    assert 0<r['probability_two_goal_lead_not_won']<1
    assert sum(x['home_goal_expectation'] for x in r['segments'])==pytest.approx(.5*3+.3*2)
    assert sum(x['away_goal_expectation'] for x in r['segments'])==pytest.approx(.5*2)
    assert sum(v for k,v in r['probabilities'].items() if k.endswith('平'))==pytest.approx(.2)

def test_one_state_predicts_no_comeback():
    p=pregame();p['score_matrix']=[{'score':'0:0','probability':1.}]
    r=predict(p,calibrate())
    assert r['probabilities']['平平']==pytest.approx(1)
    assert r['probability_two_goal_comeback_win']==pytest.approx(0)
    assert sum(x['home_goal_expectation']+x['away_goal_expectation'] for x in r['segments'])==pytest.approx(0)

def test_fit_is_not_allowed_at_or_after_prediction_cutoff():
    p=pregame();c=calibrate();c['asof_cutoff']='2026-02-02T00:00:00+08:00'
    with pytest.raises(ValueError):predict(p,c)
    c=calibrate();p['observed_at']='2026-01-04T09:00:00+08:00'
    with pytest.raises(ValueError):predict(p,c)
    c=calibrate();p=pregame();p['match_id']='dev0'
    with pytest.raises(ValueError):predict(p,c)

def test_postmatch_not_allowed_as_pregame_feature():
    p=pregame();p['actual_halftime']='0:2'
    with pytest.raises(ValueError):predict(p,calibrate())
    p=pregame();c=calibrate();c['state_factors']['home_trailing_2plus']=3
    with pytest.raises(ValueError):predict(p,c)

def test_goal_minutes_stoppage_and_invalid_event():
    assert _phase('45+5')==2 and _phase('90+4')==5
    with pytest.raises(ValueError):_phase(91)
    bad=historical();bad[0]['goal_events']=[{'minute':91,'side':'home'}]
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-02-01T00:00:00+08:00',calibration_id='x')
