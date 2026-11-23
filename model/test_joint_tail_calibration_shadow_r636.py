import copy
import math
import pytest
from joint_tail_calibration_shadow_r636 import (
    grid, aggregates, features, tilt_within_wdl, fit, predict, regime,
    MIN_TRAIN, WDL,
)

Q=[[.12,.08,.02],[.15,.13,.08],[.18,.10,.14]]

def history(n=80):
    result=[]
    for i in range(n):
        outcome=('2:2' if i%4<2 else '2:0' if i%4==2 else '0:0')
        result.append({'match_id':f'train-{i}','source_id':f'paper-{i}',
            'observed_at':'2026-01-01T12:00:00+08:00',
            'cutoff':'2026-01-01T17:00:00+08:00',
            'kickoff':'2026-01-01T18:00:00+08:00',
            'result_observed_at':'2026-01-01T21:00:00+08:00',
            'score_matrix':copy.deepcopy(Q),'actual_score':outcome,
            'authorized_for_analysis':True})
    return result

def packet():
    return {'match_id':'future-1','source_id':'snapshot-future',
        'observed_at':'2026-02-02T12:00:00+08:00',
        'cutoff':'2026-02-02T16:00:00+08:00',
        'kickoff':'2026-02-02T18:00:00+08:00',
        'score_matrix':copy.deepcopy(Q),'official_jc_line':-1}

def trained():
    return fit(history(),asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='pretrained-research-only')

def test_grid_and_score_tail_rejection():
    g=grid(Q)
    assert len(g)==9 and sum(g.values())==pytest.approx(1)
    with pytest.raises(ValueError,match='incomplete'):grid([[.5,.1],[.1,.1]])
    with pytest.raises(ValueError,match='duplicate'):grid([
        {'score':'0:0','probability':.5},{'score':'0:0','probability':.5}])
    with pytest.raises(ValueError):grid([[True]])

def test_joint_tilt_preserves_fulltime_wdl_and_probability_mass():
    g=grid(Q);before=copy.deepcopy(g)
    new=tilt_within_wdl(g,[.4,.3,.1,.2,-.4,-.1])
    assert g==before
    assert sum(new.values())==pytest.approx(1)
    old=aggregates(g,-1);changed=aggregates(new,-1)
    assert old['wdl']==pytest.approx(changed['wdl'],abs=1e-10)
    assert old['goals']!=changed['goals']
    assert changed['score_top3'] and changed['jc']

def test_no_possible_change_inside_single_score_cell():
    one=grid([{'score':'1:0','probability':1.}])
    assert tilt_within_wdl(one,[.4]*6)==pytest.approx(one)

def test_reject_malformed_weights_and_jc_lines():
    with pytest.raises(ValueError):tilt_within_wdl(grid(Q),[1.]*6)
    with pytest.raises(ValueError):aggregates(grid(Q),-.5)
    with pytest.raises(ValueError):aggregates(grid(Q),True)

def test_fit_rejects_unobserved_and_unauthorized_history():
    with pytest.raises(ValueError,match='insufficient'):fit(history(10),asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='a')
    bad=history();bad[0]['result_observed_at']='2026-02-03T00:00:00+08:00'
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='a')
    bad=history();bad[0]['authorized_for_analysis']=False
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='a')

def test_fit_rejects_duplicate_and_zero_support():
    bad=history();bad[-1]['match_id']=bad[0]['match_id']
    with pytest.raises(ValueError,match='duplicate'):fit(bad,asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='a')
    bad=history();bad[0]['actual_score']='11:0'
    with pytest.raises(ValueError):fit(bad,asof_cutoff='2026-02-02T00:00:00+08:00',calibration_id='a')

def test_fit_applies_only_preexisting_regime_and_keeps_wdl_locked():
    learned=trained();p=packet();frozen=copy.deepcopy(p)
    output=predict(p,learned)
    assert p==frozen
    assert output['formal_grant'] is None and output['production_changed'] is False
    assert output['training_n']==80
    assert output['regime']=='LOW'
    assert output['candidate']['wdl']==pytest.approx(output['original']['wdl'])
    assert output['candidate']['goals']!=output['original']['goals']
    assert sum(x['probability'] for x in output['candidate_score_grid'])==pytest.approx(1)

def test_no_postmatch_in_predict_and_future_training_block():
    f=trained();p=packet()
    with pytest.raises(ValueError,match='prematch'):predict({**p,'fulltime_result':'0:1'},f)
    with pytest.raises(ValueError):predict({**p,'observed_at':'2026-01-01T19:00:00+08:00'},f)
    with pytest.raises(ValueError):predict({**p,'kickoff':'2026-02-02T15:00:00+08:00'},f)
    with pytest.raises(ValueError):predict({**p,'match_id':'train-0'},f)
    f2=copy.deepcopy(f);f2['asof_cutoff']='2026-02-03T18:00:00+08:00'
    with pytest.raises(ValueError):predict(p,f2)

def test_unfitted_high_regime_must_fail_closed():
    p=packet();p['score_matrix']=[[0.,0.,0.,0.,0.],[0.,0.,0.,0.,0.],[0.,0.,0.,0.,0.],[0.,0.,0.,0.,0.],[0.,0.,0.,0.,1.]]
    with pytest.raises(ValueError,match='no previously fitted regime'):predict(p,trained())

def test_tails_as_7plus_bucket_not_exact_7_goals():
    g=grid([{'score':'8:1','probability':.55},{'score':'1:0','probability':.45}])
    a=aggregates(g,-1)
    assert a['goals']['7+']==pytest.approx(.55)
    assert '7+' in a['goal_top3']
    assert '7+' not in a['goal_dual']
