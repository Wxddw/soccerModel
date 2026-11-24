import pytest
from selection_risk_r636_20261124 import coverage_review,static_market_review,normalized,review_with_original_q
from copy import deepcopy
from matchday_publish_gate_r636 import WDL, GOALS
C='2026-11-24T18:00:00+08:00'; K='2026-11-25T02:00:00+08:00'; O='2026-11-24T17:59:00+08:00'

def obs(*keys):return {k:{'source_id':k,'observed_at':O} for k in keys}
def static():return dict(cutoff=C,kickoff=K,jc_wdl=[1.73,3.63,3.50],eu_wdl=[2.18,3.55,3.11],ah_home=-.25,crowd={'胜':.54,'平':.31,'负':.15},observations=obs('jc_wdl','eu_wdl','ah_home','crowd'))
def example():
    return dict(cutoff=C,kickoff=K,wdl={'胜':.5,'平':.245,'负':.255},jc={'让胜':.39,'让平':.24,'让负':.37},goals=dict(zip(GOALS,[.02,.07,.19,.23,.16,.15,.10,.08])),official_jc_line=-2,regular_open=True,wdl_pair=['胜','负'],jc_pair=['让胜','让负'],goal_top3=['3','2','4'],score_top3=['2:0','2:1','3:0'],htft=None,market_flags=['MID_FAVORITE_CROSS_MARKET_SHALLOW_REVIEW'])
def support(target):return [{'family':x,'source_id':x,'observed_at':O,'target':target} for x in ['roster','tactics']]

def test_static_moderate_favorite_shallow():
    r=static_market_review(**static()); assert 'MID_FAVORITE_CROSS_MARKET_SHALLOW_REVIEW' in r['flags'];assert not r['movement_verified'] and not r['intent_proven']
def test_crowd_excess():
    s=static();s['crowd']={'胜':.43,'平':.42,'负':.15};assert 'DRAW_BUY_EXCESS_REVIEW' in static_market_review(**s)['flags']
def test_no_fabricated_provenance():
    s=static();del s['observations']['eu_wdl'];
    with pytest.raises(ValueError):static_market_review(**s)
def test_postcutoff_market_refused():
    s=static();s['observations']['crowd']['observed_at']=K
    with pytest.raises(ValueError):static_market_review(**s)
def test_static_no_normal_market():
    s=static();s['jc_wdl']=None;del s['observations']['jc_wdl'];assert static_market_review(**s)['status']=='REGULAR_MARKET_UNAVAILABLE'
def test_review_only_and_deep_letdraw():
    x=example();before=deepcopy(x);r=coverage_review(**x);assert 'DEEP_JC_EXACT_MARGIN_PROTECTION_REVIEW' in r['flags'];assert 'DRAW_PROTECTION_REVIEW' in r['flags'];assert not r['shadow_alternatives'];assert x==before

def test_draw_challenger_requires_two_nonmarket_sources():
    x=example();r=coverage_review(**x,evidence=support('平'));assert r['shadow_alternatives']['wdl_pair']==['胜','平'];assert r['original_wdl_pair']==['胜','负'];assert not r['auto_flip']
    e=support('平');e[1]['source_id']=e[0]['source_id'];assert 'wdl_pair' not in coverage_review(**x,evidence=e)['shadow_alternatives']
def test_no_draw_challenger_from_market_alone():
    x=example();assert not coverage_review(**x)['shadow_alternatives'];x['market_flags']=[];assert not coverage_review(**x,evidence=support('平'))['shadow_alternatives']
def test_high_tail_at_most_one_slot():
    x=example();r=coverage_review(**x,evidence=support('high'));assert r['shadow_alternatives']['goal_top3']==['3','2','5'];assert r['original_goal_top3']==['3','2','4']
    assert 'goal_top3' not in coverage_review(**x,evidence=support('high')+support('low'))['shadow_alternatives']
def test_letdraw_near_second_slot():
    x=example();x['jc']={'让胜':.42,'让平':.28,'让负':.30};r=coverage_review(**x,evidence=support('让平'));assert r['shadow_alternatives']['jc_pair']==['让胜','让平']
def test_unavailable_regular():
    x=example();x['regular_open']=False
    with pytest.raises(ValueError):coverage_review(**x)
    x['wdl_pair']=None;assert 'wdl_pair' not in coverage_review(**x)['shadow_alternatives']
def test_inplay_evidence_refused():
    x=example();e=support('high');e[0]['observed_at']=K
    with pytest.raises(ValueError):coverage_review(**x,evidence=e)
def test_htft_q_marginal_enforced():
    x=example();from matchday_publish_gate_r636 import HTFT
    x['htft']={k:0. for k in HTFT};x['htft']['胜胜']=1
    with pytest.raises(ValueError):coverage_review(**x)
def test_bad_inputs_rejected():
    x=example();x['official_jc_line']=-.25
    with pytest.raises(ValueError):coverage_review(**x)
    s=static();s['jc_wdl']=[1.2,4,5,7]
    with pytest.raises(ValueError):static_market_review(**s)
def test_integration_uses_original_q():
    from test_matchday_publish_gate_r636 import pkt
    from market_trap_cold_watch_r636 import no_historical_market_packet
    from matchday_publish_gate_r636 import review
    p=pkt();r=review(p);p['published_goal_top3']=r['goal_top3_derived'];p['published_score_top3']=r['score_top3_derived'];m=no_historical_market_packet(p['match_id'],p['cutoff'],p['kickoff'],p['official_jc_line'])
    before=deepcopy(p);out=review_with_original_q(p,m,regular_open=True,wdl_pair=['胜','平'],jc_pair=['让胜','让平']);assert out['selection_research']['metrics']['letdraw_probability']==pytest.approx(.4);assert out['production_mutated'] is False and p==before

def test_away_favorite_cold_side_review_and_challenger():
    s=static();s.update(jc_wdl=[3.63,3.50,1.73],eu_wdl=[3.19,3.49,2.08],ah_home=.25,crowd={'胜':.24,'平':.26,'负':.50});r=static_market_review(**s)
    assert 'AWAY_FAVORITE_PROTECTION_FRAGILE_REVIEW' in r['flags']
    x=example();x.update(wdl={'胜':.245,'平':.255,'负':.5},wdl_pair=['负','平'],market_flags=r['flags'])
    assert not coverage_review(**x)['shadow_alternatives'];assert coverage_review(**x,evidence=support('胜'))['shadow_alternatives']['wdl_pair']==['负','胜']
def test_stale_cross_market_comparison_is_not_alert():
    s=static();s['observations']['eu_wdl']['observed_at']='2026-11-24T15:00:00+08:00';assert 'MID_FAVORITE_CROSS_MARKET_SHALLOW_REVIEW' not in static_market_review(**s)['flags']
def test_published_replay():
    from replay_nov23_published_r636 import run
    r=run();assert r['hits']['wdl_single']=={'hit':2,'n':7};assert r['hits']['jc_pair']=={'hit':6,'n':8};assert r['hits']['goal_top3']=={'hit':5,'n':8};assert not r['complete_frozen_q_available'];assert r['actual']['letdraw']==2