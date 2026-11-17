from datetime import datetime,timedelta,timezone
import math
import copy
import pytest
import candidate_models_r6313 as candidate
import calibration_r6314 as r
import joint_bridge_r6312 as joint

STAMP={'source_id':'synthetic-prior','observed_at':'2026-01-01T00:00:00+00:00','kickoff':'2026-01-02T00:00:00+00:00'}


def g(name='poisson',**kwargs):
    return candidate.generate_grid({**STAMP,'model':name,'home_lambda':1.4,'away_lambda':.9,**kwargs})['grid']


def rec(n,score,season='dev'):
    dt=(datetime(2026,2,1,tzinfo=timezone.utc) if season=='test' else datetime(2026,1,2,tzinfo=timezone.utc))+timedelta(days=n)
    return {'match_id':season+str(n),'score_matrix':g(),
            'cutoff':(dt-timedelta(hours=2)).isoformat(),
            'kickoff':dt.isoformat(),'result_score':score}


def data():return [rec(i,x) for i,x in enumerate(['1:0','2:1','2:0','1:1','0:0','3:0'])],[rec(i,x,'test') for i,x in enumerate(['1:0','2:1','3:1','0:1'])]


@pytest.mark.parametrize('axis',r.AXES)
def test_categorical_conserves_one(axis):
    assert sum(r.vector(g(),axis).values())==pytest.approx(1)


def test_margin_bin_classification():
    assert r.cat(7,1,'margin')=='3+'
    assert r.cat(0,5,'margin')=='-3-'
    assert r.cat(2,1,'margin')=='1'
    assert r.cat(1,2,'margin')=='-1'
    assert r.cat(0,0,'margin')=='0'


def test_goal_bin_classification():
    assert r.cat(5,3,'goal')=='7+'
    assert r.cat(1,0,'goal')=='1'


@pytest.mark.parametrize('line,score,actual',[
    (-1,'2:1','让平'),(1,'1:2','让平'),(-2,'2:0','让平'),
    (-1,'3:1','让胜'),(-1,'1:1','让负')])
def test_jc_exact_margin_cross_layer(line,score,actual):
    q=[{'score':score,'probability':1.}]
    s=r.score_grid(q,score,line)
    assert s['JC']['brier']==pytest.approx(0)
    assert joint.jc_label(*joint.parse_score(score),line)==actual


def test_calibrated_grid_retains_normalized_all_markets():
    dev,_=data();fit=r.fit_weights(dev,'margin',10)
    q=r.apply(g(),fit)
    assert joint.aggregate(q,-1)['joint_mass']==pytest.approx(1)
    assert sum(joint.aggregate(q,-1)['jc_probabilities'].values())==pytest.approx(1)
    assert sum(joint.aggregate(q,-1)['goal_bucket_probabilities'].values())==pytest.approx(1)
    assert fit['formal_grant'] is None


@pytest.mark.parametrize('axis',r.AXES)
def test_training_does_not_edit_raw_grid(axis):
    dev,_=data();x=copy.deepcopy(dev)
    fit=r.fit_weights(dev,axis)
    r.apply(dev[0]['score_matrix'],fit)
    assert dev==x


@pytest.mark.parametrize('axis',r.AXES)
def test_future_holdout_runs(axis):
    dev,test=data();o=r.evaluate_chronological(dev,test,axis)
    assert o['future_test_n']==4
    assert o['future_baseline']['log_loss']>=0
    assert o['future_candidate']['log_loss']>=0
    assert not o['production_changed']


def test_temporal_leakage_rejected():
    dev,test=data();test[0]['cutoff']=dev[-1]['kickoff']
    with pytest.raises(ValueError,match='overlaps'):r.check_train_test(dev,test)


def test_duplicate_fixtures_rejected():
    dev,test=data();test[0]['match_id']=dev[0]['match_id']
    with pytest.raises(ValueError,match='duplicate'):r.check_train_test(dev,test)


def test_missing_grid_rejected():
    dev,test=data();dev[0]['score_matrix']=[]
    with pytest.raises(ValueError):r.check_train_test(dev,test)


def test_future_cutoff_rejected():
    dev,test=data();test[0]['cutoff']=test[0]['kickoff']
    with pytest.raises(ValueError,match='cutoff'):r.check_train_test(dev,test)


def test_invalid_strength_rejected():
    dev,_=data()
    for value in [0,-1,float('nan'),True,float('inf')]:
        with pytest.raises(ValueError):r.fit_weights(dev,'margin',value)


def test_grid_score_is_finite_and_ht_marginal_conserved():
    q=g();s=r.score_grid(q,'2:0',-1)
    assert s['score_log_loss']>=0
    spec={**STAMP,'fraction_home':.44,'fraction_away':.45}
    ht=r.score_htft(q,'2:0','1:0',spec)
    assert ht['log_loss']>=0
    assert ht['full_time_marginal']==pytest.approx(joint.aggregate(q)['wdl_probabilities'])


def test_external_rounded_odd_timestamp_gate():
    q=g();o={**STAMP,'market_type':'WDL_DECIMAL','odds':{'胜':2.0,'平':3.4,'负':4.5}}
    out=r.compare_same_cutoff(q,o,'2026-01-01T01:00:00+00:00')
    assert out['quote_delay_seconds']==3600
    with pytest.raises(ValueError,match='after model cutoff'):
        r.compare_same_cutoff(q,o,'2025-12-31T23:00:00+00:00')


def test_half_history_provenance_and_nonleakage():
    hist=[{'kickoff':'2025-11-01T00:00:00+00:00','full_time_score':'3:2','half_time_score':'1:1'}]
    out=r.fit_halftime_prior(hist,'2026-01-01T00:00:00+00:00')
    assert 0<out['fraction_home']<1
    with pytest.raises(ValueError,match='leaks'):r.fit_halftime_prior(hist,'2025-01-01T00:00:00+00:00')


def test_narrow_warning_and_no_auto_grant():
    q=[{'score':'2:1','probability':.4},{'score':'1:1','probability':.35},{'score':'3:1','probability':.25}]
    x=r.letdraw_warning(q,-1)
    assert x['letdraw_target_margin']==1
    assert x['letdraw_probability']==pytest.approx(.4)
    assert x['formal_handicap_grant'] is None
    assert x['auto_reverse'] is False


def test_jc_uses_entire_grid_not_top3_only():
    q=[{'score':'2:1','probability':.3},{'score':'0:0','probability':.25},{'score':'1:0','probability':.2},{'score':'2:0','probability':.15},{'score':'0:1','probability':.1}]
    x=r.letdraw_warning(q,-1)
    assert x['letdraw_probability']==pytest.approx(.5)
    assert x['two_score_top3_letdraw']


def test_rps_bounds():
    q=[{'score':'1:0','probability':1}]
    o=r.score_grid(q,'1:0',-1)
    for k in ['wdl','goal','margin','JC']:
        assert o[k]['ranked_probability_score']==pytest.approx(0)


def test_invalid_positive_probs_fail_closed():
    bad=[{'score':'1:0','probability':.5}]
    with pytest.raises(ValueError):r.score_grid(bad,'1:0')


def test_r6314_inspection_baseline_no_override():
    import shadow_r6314 as shade
    from test_shadow_r637 import coherent_packet
    p=coherent_packet()
    out=shade.inspect(p)
    assert out['r6314_calibration_research']['status']=='NO_TRAINED_CALIBRATION_ATTACHED'
    assert out['formal_handicap_grant'] is None
    assert not out['production_changed']


def test_r6314_prematch_challenger_does_not_modify_original():
    import shadow_r6314 as shade
    from test_shadow_r637 import coherent_packet
    p=coherent_packet()
    fit=r.fit_weights(data()[0],'margin',10)
    p['research_fitted_calibrations_r6314']={'margin':fit}
    original=copy.deepcopy(p)
    out=shade.inspect(p)
    assert out['r6314_calibration_research']['status']=='RESEARCH_CALIBRATION_CHALLENGERS_ONLY'
    assert out['r6314_calibration_research']['candidates']['margin']['automatic_adoption'] is False
    assert p==original
    assert out['formal_handicap_grant'] is None


def test_r6314_rejects_future_fitted_calibration():
    import shadow_r6314 as shade
    from test_shadow_r637 import coherent_packet
    p=coherent_packet();fit=r.fit_weights(data()[0],'margin',10)
    fit['latest_training_kickoff']='2030-01-01T00:00:00+00:00'
    p['research_fitted_calibrations_r6314']={'margin':fit}
    with pytest.raises(ValueError,match='overlap'):shade.inspect(p)


def test_r6314_prohibits_training_labels_inside_prematch():
    import shadow_r6314 as shade
    from test_shadow_r637 import coherent_packet
    p=coherent_packet();p['result_score']='2:1'
    with pytest.raises(ValueError):shade.inspect(p)


def test_offline_benchmark_works_and_blocks_absent_optional_data():
    import benchmark_r6314 as runner
    dev,test=data()
    x=runner.run({'development':dev,'test':test})
    assert x['future_test_n']==len(test)
    assert x['GS']['status'].startswith('BLOCK')
    assert x['HTFT']['status'].startswith('BLOCK')
    assert x['Outcome']['status'].startswith('BLOCK')
    assert not x['production_changed']


def test_offline_benchmark_half_time_chronological():
    import benchmark_r6314 as runner
    dev,test=data()
    for e in dev+test:e['half_time_score']='0:0'
    x=runner.run({'development':dev,'test':test})
    assert x['HTFT']['status']=='CHRONOLOGICAL_RESEARCH_COMPARISON'
    assert x['HTFT']['prior']['historical_n']==len(dev)


def test_offline_benchmark_bad_odds_refuses_leakage():
    import benchmark_r6314 as runner
    dev,test=data()
    for e in test:
        e['market_snapshot']={**STAMP,'observed_at':e['kickoff'],'kickoff':e['kickoff'],
          'market_type':'WDL_DECIMAL','odds':{'胜':2.,'平':3.5,'负':4.}}
    with pytest.raises(ValueError,match='after model cutoff'):runner.run({'development':dev,'test':test})


def test_offline_benchmark_gs_four_models_candidate():
    import benchmark_r6314 as runner
    dev,test=data()
    for row in dev+test:
        base={'source_id':'synthetic-param','observed_at':row['cutoff'],'kickoff':row['kickoff'],
              'home_lambda':1.4,'away_lambda':.9}
        row['candidate_specs']={
          'poisson':{**base,'model':'poisson'},
          'dixon_coles':{**base,'model':'dixon_coles','rho':-.08},
          'negative_binomial':{**base,'model':'negative_binomial','size_home':10.,'size_away':10.},
          'bivariate_poisson':{**base,'model':'bivariate_poisson','covariance':.2}}
    x=runner.run({'development':dev,'test':test})
    assert x['GS']['status']=='CHRONOLOGICAL_RESEARCH_COMPARISON'
    assert set(x['GS']['candidate_results'])==set(candidate.MODELS)


def test_offline_benchmark_jc_requires_actual_integer_line():
    import benchmark_r6314 as runner
    dev,test=data()
    for row in test:row['official_jc_integer_line']=-1
    x=runner.run({'development':dev,'test':test})
    assert x['JC']['n']==4
    assert x['JC']['no_automatic_direction_change']
