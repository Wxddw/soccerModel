"""R636 Nov22 additive gates: functional tests only, NOT model accuracy tests."""
import copy
import math
import pytest
from matchday_publish_gate_r636 import HTFT
from r636_exposure_guards_20261122 import (prematch_exposure_review,batch_exposure_review,
                                          _distinct_family_source_pairs)
from test_matchday_publish_gate_r636 import pkt, Q, O, C, T


def signal(family,tail,source=None,t=O):
    return {'family':family,'tail':tail,'source_id':source or family,'observed_at':t}


def test_exact_margin_letdraw_and_provenance():
    p=pkt();before=copy.deepcopy(p)
    r=prematch_exposure_review(p)
    assert p==before
    assert r['jc_exact_margin']['letdraw_exact_margin']==1
    assert r['jc_exact_margin']['letdraw_probability']==pytest.approx(.4)
    assert r['jc_exact_margin']['ranked_jc'][0]=='让胜'
    assert r['jc_exact_margin']['letdraw_rank']==2
    assert r['jc_exact_margin']['one_goal_margin_home']==pytest.approx(.4)
    assert r['goal_families']['central_2_3']==pytest.approx(.7)
    assert r['score_top3_mass']==pytest.approx(.7)
    assert r['goal_top3_mass']==pytest.approx(.9)
    assert r['production_weights_modified'] is False and r['formal_grant'] is None
    assert len(r['original_prematch_packet_sha256'])==64


def test_tail_one_market_signal_cannot_activate():
    s=[signal('market','high','odds'),signal('market','high','bifa')]
    o=prematch_exposure_review(pkt(),tail_evidence=s)['goal_tail_evidence']
    assert o['matched_independent_families_and_sources']['high']==1
    assert o['high_evidence_gate'] is False


def test_tail_two_families_one_source_never_double_count():
    s=[signal('market','high','same'),signal('roster','high','same')]
    o=prematch_exposure_review(pkt(),tail_evidence=s)['goal_tail_evidence']
    assert o['matched_independent_families_and_sources']['high']==1
    assert not o['high_evidence_gate']


def test_tail_independent_two_families_review_only():
    p=pkt(); old=copy.deepcopy(p)
    s=[signal('roster','low','roster-news'),signal('tactics','low','coach-press')]
    r=prematch_exposure_review(p,tail_evidence=s)
    assert r['goal_tail_evidence']['low_evidence_gate'] is True
    assert r['goal_tail_evidence']['automatic_reweighting'] is False
    assert r['original_goal_top3_unchanged']==old['published_goal_top3']
    assert p==old


def test_simultaneous_high_low_conflicts_freeze_original_peak():
    s=[signal('roster','low','a'),signal('tactics','low','b'),
       signal('market','high','c'),signal('schedule','high','d')]
    r=prematch_exposure_review(pkt(),tail_evidence=s)
    assert 'CONFLICT' in r['goal_tail_evidence']['status']
    assert not r['goal_tail_evidence']['low_evidence_gate']
    assert not r['goal_tail_evidence']['high_evidence_gate']
    assert r['original_goal_top3_unchanged']==['2','3','1']


def test_tail_event_timestamp_and_schema_fail_closed():
    with pytest.raises(ValueError,match='postcutoff'):
        prematch_exposure_review(pkt(),tail_evidence=[signal('schedule','low','late',T)])
    with pytest.raises(ValueError,match='fields'):
        prematch_exposure_review(pkt(),tail_evidence=[{**signal('schedule','low'),'actual_score':'0:0'}])
    with pytest.raises(ValueError,match='duplicate'):
        prematch_exposure_review(pkt(),tail_evidence=[signal('schedule','low'),signal('schedule','low')])
    with pytest.raises(ValueError):
        prematch_exposure_review({**pkt(),'actual_result':'0:0'})


def test_HTFT_risk_states_are_descriptive_not_top2_reorder():
    p=pkt();p['htft_probabilities']={k:0. for k in HTFT}
    p['htft_probabilities'].update({'胜胜':.60,'平胜':.30,'平平':.07,'负平':.03})
    p['published_htft']=['胜胜','平胜']
    r=prematch_exposure_review(p)
    risk=r['htft_state_distribution']
    assert risk['status']=='SHADOW_FT_MARGINALS_CONSISTENT'
    assert risk['nine_class_diagnostics']['from_half_time_trailing_to_draw_or_win']==pytest.approx(.03)
    assert risk['nine_class_diagnostics']['平平']==pytest.approx(.07)
    assert risk['top2_probability_mass']==pytest.approx(.90)
    assert r['original_htft_top2_unchanged']==['胜胜','平胜']


def test_missing_nine_class_wont_fabricate_htft_prediction():
    r=prematch_exposure_review(pkt())
    assert r['htft_state_distribution']['top2_probability_mass'] is None
    assert r['htft_state_distribution']['status'].startswith('BLOCK_NO')
    assert r['original_component_release_gates']['HTFT']=='BLOCK_NO_NINE_CLASS'


def test_other_market_missing_is_blocked_only_affected_play():
    p=pkt();p['official_jc_line']=None;p['jc_observation']=None
    r=prematch_exposure_review(p)
    assert r['jc_exact_margin']['status'].startswith('BLOCK')
    assert r['original_component_release_gates']['JC']=='BLOCK_OFFICIAL_LINE_MISSING'
    assert r['original_component_release_gates']['Score']=='SHADOW_CONSISTENT'


def test_AIC_always_zero_numeric_delta_and_reject_inmatch():
    rec={'player_id':'gk','role':'GK','availability_state':'out',
         'expected_minutes':0,'replacement_id':'backup','replacement_role':'GK',
         'source_id':'press','observed_at':O}
    r=prematch_exposure_review(pkt(),aic_records=[rec])
    assert r['aic']['numeric_xg_delta'] is None
    with pytest.raises(ValueError):
        prematch_exposure_review(pkt(),aic_records=[{**rec,'actual_injury_minute':37}])


def test_zero_and_high_tail_exposure_and_draws_detect_batch_not_force():
    p=[]
    for i in range(8):p.append(prematch_exposure_review(pkt(f'{i:03d}')))
    b=batch_exposure_review(p)
    assert b['sum_of_prematch_wdl_probabilities']['平']==pytest.approx(.8)
    assert b['expected_jc_letdraw_count']==pytest.approx(3.2)
    assert 'NO_LETDRAW_TOP1_DESPITE_EXACT_MARGIN_MASS_REVIEW_ONLY' in b['flags']
    assert b['selected_wdl_count']['胜']==8
    assert b['original_predictions_unchanged']


def test_batch_detection_of_high_zero_and_draw_exposure():
    p=[]
    for i in range(8):
        packet=pkt(f'{i:03d}');packet['score_grid']=[
            {'score':'0:0','probability':.2},{'score':'1:0','probability':.25},
            {'score':'2:1','probability':.30},{'score':'3:2','probability':.25}]
        packet['published_score_top3']=['2:1','1:0','3:2']
        packet['published_goal_top3']=['3','1','5']
        packet['frozen_wdl']='胜'
        p.append(prematch_exposure_review(packet))
    b=batch_exposure_review(p)
    assert b['goal_bucket_exposure']['0']['expected_matches']==pytest.approx(1.6)
    assert 'ZERO_GOAL_TOP3_COVERAGE_NONE_REVIEW_ONLY' in b['flags']
    assert 'NO_DRAW_TOP1_DESPITE_EXPECTED_DRAW_MASS_REVIEW_ONLY' in b['flags']


def test_duplicate_batch_blocks():
    a=prematch_exposure_review(pkt())
    with pytest.raises(ValueError,match='duplicate'):
        batch_exposure_review([a,a])


def test_signal_matcher_with_ambiguous_shared_source():
    assert _distinct_family_source_pairs({('market','shared'),('roster','shared'),('tactics','other')})==2
    assert _distinct_family_source_pairs({('market','shared'),('roster','shared')})==1


def test_htft_nine_class_batch_exposure_from_frozen_proba():
    p=[]
    for i in range(8):
        x=pkt(f'{i:03d}');x['htft_probabilities']={k:0. for k in HTFT}
        x['htft_probabilities'].update({'胜胜':.6,'平胜':.3,'平平':.07,'负平':.03})
        x['published_htft']=['胜胜','平胜']
        p.append(prematch_exposure_review(x))
    b=batch_exposure_review(p)
    assert b['htft_proper_probabilities_available_n']==8
    assert b['htft_nine_class_expected_counts']['负平']==pytest.approx(.24)
    assert b['htft_nine_class_expected_counts']['平平']==pytest.approx(.56)
    assert b['htft_class_top2_inclusion_counts']['负平']==0
    assert b['htft_class_top2_inclusion_counts']['胜胜']==8


def test_htft_batch_stats_not_guessed_when_partial():
    a=prematch_exposure_review(pkt('a'))
    b=pkt('b');b['htft_probabilities']={k:0. for k in HTFT}
    b['htft_probabilities'].update({'胜胜':.6,'平胜':.3,'平平':.1})
    b['published_htft']=['胜胜','平胜']
    z=batch_exposure_review([a,prematch_exposure_review(b)])
    assert z['htft_nine_class_expected_counts'] is None
    assert z['htft_proper_probabilities_available_n']==1