import copy
import math
import pytest
from htft_segment_hazard_r636 import predict,fit,_phase,PHASES,PATHS

T='2026-11-20T18:30:00+08:00'
C='2026-11-20T17:45:00+08:00'
O='2026-11-20T17:30:00+08:00'
L='2026-11-19T23:00:00+08:00'
SPEC={'source_id':'frozen-snapshot-id','calibration_id':'authorized-development-42',
      'observed_at':O,'cutoff':C,'kickoff':T,'latest_training_result_observed_at':L,
      'home_xg':1.4,'away_xg':1.2,'home_shares':[1/6]*6,'away_shares':[1/6]*6,
      'state_factors':{k:1. for k in ('home_leading','home_trailing','away_leading','away_trailing')}}

def q(*items):return [{'score':sc,'probability':pr} for sc,pr in items]

def test_00_forces_draw_draw_and_zero_goals():
    x=predict(q(('0:0',1.)),SPEC)
    assert x['probabilities']['平平']==pytest.approx(1.)
    assert sum(z['total_expected_goals'] for z in x['segments'])==pytest.approx(0)
    assert x['research_only'] and not x['production_changed'] and x['formal_grant'] is None

def test_one_goal_exact_six_way_timing_and_half_probability():
    x=predict(q(('1:0',1.)),SPEC)
    assert x['probabilities']['胜胜']==pytest.approx(.5,abs=1e-10)
    assert x['probabilities']['平胜']==pytest.approx(.5,abs=1e-10)
    assert x['full_time_wdl']==pytest.approx({'胜':1,'平':0,'负':0})
    assert [z['home_expected_goals'] for z in x['segments']]==pytest.approx([1/6]*6,abs=1e-10)
    assert sum(z['away_expected_goals'] for z in x['segments'])==pytest.approx(0)

def test_fulltime_joint_mass_and_period_sum_unchanged():
    Q=q(('0:0',.13),('1:0',.2),('2:1',.22),('0:2',.1),('2:2',.15),('3:1',.2))
    frozen=copy.deepcopy(Q)
    spec=copy.deepcopy(SPEC)
    spec['state_factors']={'home_leading':.75,'home_trailing':1.25,
                           'away_leading':.8,'away_trailing':1.3}
    out=predict(Q,spec)
    assert Q==frozen and math.fsum(out['probabilities'].values())==pytest.approx(1)
    assert out['full_time_wdl']==pytest.approx({'胜':.62,'平':.28,'负':.1})
    assert sum(z['home_expected_goals'] for z in out['segments'])==pytest.approx(1.54)
    assert sum(z['away_expected_goals'] for z in out['segments'])==pytest.approx(.92)
    assert len(out['probabilities'])==9 and len(out['top3'])==3

def test_trailing_changes_paths_without_changing_frozen_Q():
    Q=q(('2:1',1.));base=predict(Q,SPEC)
    spec=copy.deepcopy(SPEC)
    spec['state_factors']['home_leading']=.6
    spec['state_factors']['away_trailing']=1.6
    new=predict(Q,spec)
    assert new['full_time_wdl']==pytest.approx(base['full_time_wdl'])
    assert new['probabilities'] != base['probabilities']

def test_fail_closed_temporal_and_incomplete_grid():
    with pytest.raises(ValueError,match='mass'):predict(q(('1:0',.6)),SPEC)
    with pytest.raises(ValueError):predict(q(('1:0',.5),('1:0',.5)),SPEC)
    with pytest.raises(ValueError):predict(q(('1:0',1.)),{**SPEC,'actual_score':'1:0'})
    with pytest.raises(ValueError):predict(q(('1:0',1.)),{**SPEC,'observed_at':T})
    with pytest.raises(ValueError):predict(q(('1:0',1.)),{**SPEC,'latest_training_result_observed_at':T})
    with pytest.raises(ValueError):predict(q(('1:0',1.)),{**SPEC,'state_factors':{'home_leading':3}})
    with pytest.raises(ValueError):predict(q(('1:0',1.)),{**SPEC,'home_shares':[.4]*6})

def history(i,period='dev',goal_min=46,ht='0:0'):
    day=i+1
    mo=10 if period=='dev' else 11
    kickoff=f'2026-{mo:02d}-{day:02d}T19:00:00+08:00'
    return {'match_id':f'{period}-{i}', 'observed_at':f'2026-{mo:02d}-{day:02d}T16:00:00+08:00',
            'cutoff':f'2026-{mo:02d}-{day:02d}T18:00:00+08:00','kickoff':kickoff,
            'result_observed_at':f'2026-{mo:02d}-{day:02d}T21:30:00+08:00',
            'home_xg':1.5,'away_xg':1.1,'full_time_score':'1:0','half_time_score':ht,
            'goal_events':[{'minute':goal_min,'side':'home'}]}

def test_fit_events_and_result_availability_no_leakage():
    H=[history(i) for i in range(10)]
    x=fit(H,asof_cutoff='2026-11-20T16:00:00+08:00')
    assert x['development_n']==10
    assert x['home_shares'][3]>x['home_shares'][1]
    assert sum(x['home_shares'])==pytest.approx(1)
    assert sum(x['away_shares'])==pytest.approx(1)
    bad=copy.deepcopy(H);bad[0]['result_observed_at']='2026-11-21T00:00:00+08:00'
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-11-20T16:00:00+08:00')
    bad=copy.deepcopy(H);bad[0]['half_time_score']='1:0'
    with pytest.raises(ValueError,match='reconcile'):fit(bad,asof_cutoff='2026-11-20T16:00:00+08:00')
    bad=copy.deepcopy(H);bad[0]['goal_events'].append({'minute':94,'side':'away'})
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-11-20T16:00:00+08:00')

def test_injury_time_phase_mapping():
    assert _phase('45+3')==2 and _phase('90+8')==5
    assert _phase(45)==2 and _phase(46)==3
    with pytest.raises(ValueError):_phase(91)
