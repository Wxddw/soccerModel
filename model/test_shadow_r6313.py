"""GitHub-inspired research-channel conservation and no-hindsight tests."""
import copy
import math
from datetime import datetime,timedelta,timezone
import pytest

import candidate_models_r6313 as candidate
import halftime_bridge_r6313 as half
import market_audit_r6313 as market
import shadow_r6313 as shadow
import forward_validation_r6313 as validator
import joint_bridge_r6312 as joint
from test_shadow_r6311 import future_packet
from test_shadow_r637 import coherent_packet


def stamps():
    return {'source_id':'test-prematch-only','observed_at':'2026-11-17T10:00:00+08:00',
            'kickoff':'2026-11-17T20:00:00+08:00'}


def model(model_name='poisson',**kw):
    return {**stamps(),'model':model_name,'home_lambda':1.4,'away_lambda':.9,**kw}


def future_specs():
    p,t=future_packet()
    s={ 'source_id':'research-source','observed_at':(t-timedelta(minutes=15)).isoformat(),
         'kickoff':p['kickoff'] }
    p['research_candidate_model']={**s,'model':'poisson','home_lambda':1.5,'away_lambda':.9}
    p['research_htft']={**s,'fraction_home':.44,'fraction_away':.46}
    p['research_market_odds']={**s,'market_type':'WDL_DECIMAL','odds':{'胜':1.75,'平':3.6,'负':4.8}}
    return p,t


@pytest.mark.parametrize('name,kwargs',[
    ('poisson',{}),('dixon_coles',{'rho':-.07}),
    ('negative_binomial',{'size_home':35.,'size_away':45.}),
    ('bivariate_poisson',{'covariance':.25}),
    ('bivariate_poisson',{'covariance':0.})])
def test_four_model_families_normalize_and_share_bridge(name,kwargs):
    x=candidate.generate_grid(model(name,**kwargs))
    assert len(x['grid'])==121
    assert x['probability_sum']==pytest.approx(1)
    assert x['omitted_tail_mass_before_normalization']<=.002
    j=joint.aggregate(x['grid'],-1)
    assert sum(j['wdl_probabilities'].values())==pytest.approx(1)
    assert sum(j['goal_bucket_probabilities'].values())==pytest.approx(1)
    assert sum(j['jc_probabilities'].values())==pytest.approx(1)
    assert not x['official_model_changed']


@pytest.mark.parametrize('name,kwargs',[
    ('poisson',{}),('dixon_coles',{'rho':0}),('bivariate_poisson',{'covariance':0})])
def test_zero_correlation_models_equal_independence(name,kwargs):
    base=candidate.generate_grid(model('poisson'))['grid']
    x=candidate.generate_grid(model(name,**kwargs))['grid']
    for u,v in zip(base,x):assert u['probability']==pytest.approx(v['probability'],abs=1e-12)


def test_dc_negative_rho_lifts_low_draw_probability():
    raw=candidate.generate_grid(model())['grid']
    dc=candidate.generate_grid(model('dixon_coles',rho=-.08))['grid']
    r={x['score']:x['probability'] for x in raw};d={x['score']:x['probability'] for x in dc}
    assert d['0:0']>r['0:0'];assert d['1:1']>r['1:1']
    assert d['1:0']<r['1:0'];assert d['0:1']<r['0:1']
    assert d['2:0']==pytest.approx(r['2:0'])


def test_bivariate_common_shock_increases_score_correlation():
    base=joint.aggregate(candidate.generate_grid(model())['grid'])
    cov=joint.aggregate(candidate.generate_grid(model('bivariate_poisson',covariance=.25))['grid'])
    assert cov['wdl_probabilities']['平']>base['wdl_probabilities']['平']


def test_negbin_dispersion_tends_to_poisson_at_large_size():
    p=joint.aggregate(candidate.generate_grid(model())['grid'])
    z=joint.aggregate(candidate.generate_grid(model('negative_binomial',size_home=1e8,size_away=1e8))['grid'])
    assert z['wdl_probabilities']==pytest.approx(p['wdl_probabilities'],abs=1e-7)


@pytest.mark.parametrize('changes',[
    {'home_lambda':-1}, {'away_lambda':float('nan')}, {'model':'unknown'},
    {'rho':.1}, {'covariance':.2}, {'size_home':4},
    {'observed_at':'2026-11-18T10:00:00+08:00'},
    {'observed_at':'2026-11-17T10:00:00'},
    {'source_id':''}, {'home_lambda':99},
    {'research_actual_score':'2:1'}
])
def test_poisson_bad_spec_fails_closed(changes):
    with pytest.raises(ValueError):candidate.generate_grid({**model(),**changes})


@pytest.mark.parametrize('changes',[
    {'rho':2.}, {'rho':None}, {'rho':float('inf')},
])
def test_bad_dc_fails_closed(changes):
    with pytest.raises(ValueError):candidate.generate_grid({**model('dixon_coles'),**changes})


@pytest.mark.parametrize('changes',[
    {'covariance':1.}, {'covariance':-.1}, {'covariance':float('nan')},
])
def test_bad_bivariate_covariance_fails_closed(changes):
    with pytest.raises(ValueError):candidate.generate_grid({**model('bivariate_poisson'),**changes})


def test_large_goal_tail_cannot_be_normalized_silently():
    with pytest.raises(ValueError,match='grid drops'):
        candidate.generate_grid({**model(),'home_lambda':5.0})


def test_simple_one_score_half_ft_distribution_exact():
    x=half.aggregate_htft([{'score':'1:0','probability':1.}],
       fraction_home=.4,fraction_away=.5,**stamps())
    assert x['probabilities']['胜胜']==pytest.approx(.4)
    assert x['probabilities']['平胜']==pytest.approx(.6)
    assert x['full_time_wdl']['胜']==pytest.approx(1)
    assert sum(x['probabilities'].values())==pytest.approx(1)
    assert len(x['probabilities'])==9


def test_0_0_half_ft_must_be_draw_draw():
    x=half.aggregate_htft([{'score':'0:0','probability':1.}],
       fraction_home=.44,fraction_away=.44,**stamps())
    assert x['probabilities']['平平']==pytest.approx(1)


def test_fulltime_wdl_exactly_preserved_by_ht_bridge():
    m=candidate.generate_grid(model())['grid']
    w=joint.aggregate(m)['wdl_probabilities']
    x=half.aggregate_htft(m,fraction_home=.44,fraction_away=.47,**stamps())
    assert x['full_time_wdl']==pytest.approx(w,abs=1e-12)
    assert sum(x['first_half_wdl'].values())==pytest.approx(1)
    assert sum(x['probabilities'].values())==pytest.approx(1)


@pytest.mark.parametrize('prob',[0,1,-.1,1.1,float('nan'),float('inf'),True])
def test_invalid_fraction_blocks(prob):
    with pytest.raises(ValueError):half.aggregate_htft([{'score':'1:0','probability':1.}],
       fraction_home=prob,fraction_away=.5,**stamps())


def test_market_de_vig_two_methods_and_no_injection():
    raw={**stamps(),'market_type':'WDL_DECIMAL','odds':{'胜':1.4,'平':4.2,'负':9.0}}
    x=market.devig(raw,{'胜':.6,'平':.25,'负':.15})
    assert x['overround']>0
    assert x['power_exponent']>1
    assert sum(x['multiplicative'].values())==pytest.approx(1)
    assert sum(x['power'].values())==pytest.approx(1)
    assert x['power']['胜']>x['multiplicative']['胜']
    assert x['model_minus_multiplicative']['胜']==pytest.approx(.6-x['multiplicative']['胜'])
    assert x['moves_production_probabilities'] is False


def test_fair_odds_lead_to_same_two_methods():
    o={'胜':3.,'平':3.,'负':3.}
    x=market.devig({**stamps(),'market_type':'WDL_DECIMAL','odds':o})
    assert x['overround']==pytest.approx(0)
    assert x['power_exponent']==pytest.approx(1,abs=1e-10)
    assert x['power']==pytest.approx(x['multiplicative'])


@pytest.mark.parametrize('bad_odds',[
    {'胜':1,'平':3,'负':4}, {'胜':-2,'平':3,'负':4},
    {'胜':2,'平':3}, {'胜':float('nan'),'平':3,'负':4},
    {'胜':True,'平':3,'负':4}
])
def test_market_bad_quotes_rejected(bad_odds):
    with pytest.raises(ValueError):
        market.devig({**stamps(),'market_type':'WDL_DECIMAL','odds':bad_odds})


def test_market_is_not_jc_or_asian_push():
    with pytest.raises(ValueError):market.devig({**stamps(),'market_type':'ASIAN_HANDICAP','odds':{'胜':2,'平':3,'负':4}})


def test_all_three_research_channels_integrated_and_frozen_production():
    p,_=future_specs(); old=copy.deepcopy(p)
    o=shadow.inspect(p)
    assert p==old
    assert o['version']==shadow.VERSION
    assert o['research_candidate_grid_diagnostics_r6313']['status']=='RESEARCH_CANDIDATE_GRID_VALIDATED'
    assert o['research_candidate_grid_diagnostics_r6313']['candidate_score_top3']
    assert o['HTFT_conditional_transition_r6313']['status']=='RESEARCH_HTFT_LINKED'
    assert o['market_devig_r6313']['status']=='READ_ONLY_MARKET_BENCHMARK'
    assert o['formal_handicap_grant'] is None
    assert o['formal_core_grant'] is None
    assert o['production_changed'] is False
    assert o['outcome_probabilities_unchanged']==[.5,.3,.2]


def test_no_optional_inputs_do_not_invent_half_time_or_market():
    o=shadow.inspect(coherent_packet())
    assert o['HTFT_conditional_transition_r6313']['status'].startswith('BLOCK')
    assert o['market_devig_r6313']['status']=='NO_PREMATCH_MARKET_SNAPSHOT'
    assert o['research_candidate_grid_diagnostics_r6313']['status']=='NOT_REQUESTED'


def test_candidate_does_not_fill_missing_frozen_q():
    from test_motivation_squad_r634 import pkt
    p=pkt()
    p['research_candidate_model']={**model(),'kickoff':p['kickoff'],'observed_at':p['cutoff']}
    o=shadow.inspect(p)
    assert o['S4_GS_RC_unified_probability_bridge_v312']['status'].startswith('UNKNOWN')
    assert 'CANDIDATE_CAN_NOT_REPLACE_MISSING_FROZEN_BASE_GRID' in o['research_flags_r6313']


def test_market_after_cutoff_blocks_before_prediction():
    p,_=future_specs()
    p['research_market_odds']['observed_at']=(candidate._asof(p['cutoff'])+timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError,match='later than declared cutoff'):shadow.inspect(p)


def test_wrong_fixture_kickoff_blocks_research():
    p,_=future_specs();p['research_htft']['kickoff']='2027-01-01T00:00:00+00:00'
    with pytest.raises(ValueError,match='kickoff must match'):shadow.inspect(p)


def test_research_prevents_postmatch_injection():
    p,_=future_specs();p['actual_score']='2:1'
    with pytest.raises(ValueError):shadow.inspect(p)


def test_forward_rps_and_score_log_stay_outside_prematch():
    p,t=future_specs();s=validator.freeze(p,now=t)
    assert s['htft']['status']=='RESEARCH_HTFT_LINKED'
    actual={'match_id':p['id'],'score':'2:0', 'observed_at':(t+timedelta(hours=5)).isoformat(),
            'source_id':'official-final-source','status':'final_90min','half_time_score':'1:0',
            'half_time_source_id':'official-halftime-source'}
    o=validator.evaluate(s,actual)
    assert o['wdl_ranked_probability_score']>=0
    assert o['goal_ranked_probability_score']>=0
    assert o['exact_score_log_loss']==pytest.approx(-math.log(.2))
    assert o['htft_log_loss']>=0
    assert o['market_brier_benchmarks']['power']>=0
    assert validator.summary([o])['matches']==1
    assert not validator.summary([o])['independent_external_frozen_samples_at_least_50']


def test_snapshot_mutation_rejected():
    p,t=future_specs();s=validator.freeze(p,now=t)
    s['htft']['top3']=['胜胜']
    a={'match_id':p['id'],'score':'2:0','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official','status':'final_90min'}
    with pytest.raises(ValueError,match='hash mismatch'):validator.evaluate(s,a)


def test_future_snapshot_fails():
    p,t=future_specs()
    with pytest.raises(ValueError,match='after kickoff'):
        validator.freeze(p,now=t+timedelta(hours=4))


def test_halftime_score_not_after_fulltime_or_uncited():
    p,t=future_specs();s=validator.freeze(p,now=t)
    a={'match_id':p['id'],'score':'1:0','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official','status':'final_90min','half_time_score':'2:0','half_time_source_id':'official'}
    with pytest.raises(ValueError,match='cannot exceed'):validator.evaluate(s,a)
    del a['half_time_source_id']
    with pytest.raises(ValueError,match='supplied together'):validator.evaluate(s,a)


def test_halftime_not_found_does_not_score_it():
    p,t=future_specs();s=validator.freeze(p,now=t)
    a={'match_id':p['id'],'score':'2:0','observed_at':(t+timedelta(hours=5)).isoformat(),
       'source_id':'official','status':'final_90min'}
    r=validator.evaluate(s,a)
    assert r['htft_log_loss'] is None and r['htft_top3_hit'] is None


def test_prematch_spec_does_not_modify_frozen_1x2_or_grid():
    p,_=future_specs(); before=copy.deepcopy(p['score_matrix'])
    q=shadow.inspect(p)
    assert p['score_matrix']==before
    assert q['S4_GS_RC_unified_probability_bridge_v312']['raw_score_top3']==['2:0','2:2','1:0']
    assert q['probability_adjustment_applied'] is False


def test_rps_correct_onehot_zero():
    assert validator._rps({'胜':1.,'平':0.,'负':0.},'胜',joint.WDL)==pytest.approx(0)
    assert validator._rps({'胜':1.,'平':0.,'负':0.},'负',joint.WDL)==pytest.approx(1)
