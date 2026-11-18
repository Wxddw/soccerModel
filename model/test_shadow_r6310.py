import copy
import json
from pathlib import Path
import pytest

from shadow_r6310 import inspect
from replay_conversation_r6310 import audit_recap
from test_shadow_r639 import jc_pkt
from test_shadow_r637 import coherent_packet
from test_motivation_squad_r634 import pkt, BEFORE


def context(kind='competitive', objective='unknown', substitutions=None, stamp=BEFORE):
    return {'source_id':'competition-official-document', 'observed_at':stamp,
            'competition_kind':kind, 'selected_side_objective':objective,
            'allowed_substitutions':substitutions}


def test_inherited_probabilities_predictions_not_mutated():
    p=jc_pkt(-1,'让负'); frozen=copy.deepcopy(p)
    result=inspect(p)
    assert p==frozen
    assert result['outcome_probabilities_unchanged']==[.5,.3,.2]
    assert result['version'].endswith('R6.3.10_20261114')
    assert result['production_changed'] is False
    assert result['probability_adjustment_applied'] is False
    assert result['postmatch_training_performed'] is False
    for key in ('formal_single_grant','formal_core_grant','formal_protection_grant','formal_handicap_grant'):
        assert result[key] is None
    assert result['GS1_6_score_concentration_review']['score_top3_unchanged']==result['GS1_7_score_family_coverage_audit']['score_top3_unchanged']


@pytest.mark.parametrize('line,expected_margin,expected_p',[
    (-3,3,0),(-2,2,.30),(-1,1,.10),(1,-1,.08),(2,-2,.07),(3,-3,0),
])
def test_exact_signed_let_draw_for_all_integer_lines(line, expected_margin, expected_p):
    a=inspect(jc_pkt(line,'让负'))['S4_v2_0_signed_margin_boundary_audit']
    assert a['signed_let_draw_margin']==expected_margin
    assert a['exact_let_draw_probability']==pytest.approx(expected_p)
    assert sum(a['reconstructed_jc_probabilities'].values())==pytest.approx(1)
    assert a['frozen_pick_unchanged']=='让负'
    assert a['formal_handicap_grant'] is None


def test_boundary_neighbors_and_all_margin_probabilities_aggregate():
    a=inspect(jc_pkt(-1, '让负'))['S4_v2_0_signed_margin_boundary_audit']
    assert a['neighbor_margin_probabilities']['1']['probability']==pytest.approx(.10)
    assert a['neighbor_margin_probabilities']['0']['probability']==pytest.approx(.30)
    assert a['neighbor_margin_probabilities']['2']['probability']==pytest.approx(.30)
    assert sum(a['signed_margin_probabilities'].values())==pytest.approx(1)


def test_no_let_draw_forced_from_top_score_example():
    a=inspect(jc_pkt(-1,'让负'))['S4_v2_0_signed_margin_boundary_audit']
    assert a['integrated_jc_first']=='让负'
    assert a['auto_let_draw_boost'] is False
    assert a['auto_pick_switch'] is False
    assert a['review_required'] is True


def test_no_official_jc_does_not_fabricate_odds_or_line():
    a=inspect(coherent_packet())['S4_v2_0_signed_margin_boundary_audit']
    assert a['status'].startswith('UNKNOWN')
    assert a['signed_margin_probabilities'] is None


def test_zero_one_five_sevenplus_bucket_aggregation():
    x=inspect(coherent_packet())['RC2_7_zero_one_four_five_seven_tail_audit']
    tail=x['tail_family_probabilities']
    assert tail['zero']==pytest.approx(.05)
    assert tail['one']==pytest.approx(.18)
    assert tail['four']==pytest.approx(.35)
    assert tail['seven_plus_aggregate']==pytest.approx(.05)
    assert tail['low_0_1']==pytest.approx(.23)
    assert tail['central_2_3']==pytest.approx(.37)
    assert tail['high_5_plus']==pytest.approx(.05)
    assert x['seven_plus_is_aggregate_not_exact_goal'] is True
    assert x['goal_top3_reordered'] is False


def test_missing_goal_dist_is_unknown():
    a=inspect(pkt())['RC2_7_zero_one_four_five_seven_tail_audit']
    assert a['status'].startswith('UNKNOWN')
    assert a['tail_family_probabilities'] is None


def test_score_family_coverage_btts_and_nilnil():
    a=inspect(coherent_packet())['GS1_7_score_family_coverage_audit']
    assert a['global_score_top3_mass']==pytest.approx(.45)
    assert a['both_teams_score_probability']==pytest.approx(.35)
    assert a['nil_nil_probability']==pytest.approx(.05)
    assert a['home_zero_goal_probability']==pytest.approx(.25)
    assert a['away_zero_goal_probability']==pytest.approx(.45)
    assert a['seven_plus_aggregate_on_matrix']==pytest.approx(.05)
    assert a['score_top3_reranked'] is False
    assert a['score_top3_family_coverage']['胜']['family_mass']==pytest.approx(.5)
    assert a['score_top3_family_coverage']['胜']['covered_by_global_score_top3_mass']==pytest.approx(.3)


def test_no_score_matrix_no_btts_fabrication():
    a=inspect(pkt())['GS1_7_score_family_coverage_audit']
    assert a['status'].startswith('UNKNOWN')
    assert a['score_top3_family_coverage'] is None


def test_friendly_with_extended_subs_is_context_watch_not_prob_change():
    p=pkt(p=(.75,.14,.11));p['competition_context']=context('friendly','unknown',11)
    x=inspect(p)
    assert x['Selection_Context_v0_8']['core_manual_review'] is True
    assert 'FRIENDLY_EXTENDED_SUBSTITUTION_ALLOWANCE_WATCH' in x['audit_flags_r6310']
    assert x['Selection_Context_v0_8']['risk_family_votes_added']==0
    assert x['outcome_probabilities_unchanged']==[.75,.14,.11]


def test_draw_sufficient_objective_review_does_not_force_draw_probability():
    p=pkt(p=(.76,.15,.09));p['competition_context']=context('competitive','draw_sufficient')
    o=inspect(p)
    assert o['Selection_Context_v0_8']['core_manual_review'] is True
    assert o['outcome_probabilities_unchanged']==[.76,.15,.09]
    assert o['Selection_Efficiency_v0_8']['raw_direction']=='胜'


def test_context_absence_is_unknown_not_safe():
    x=inspect(pkt())['Selection_Context_v0_8']
    assert x['status'].startswith('UNKNOWN')
    assert x['core_manual_review'] is False


def test_context_not_needed_to_fake_nonexistent_qualification():
    p=pkt();p['competition_context']=context('competitive','unknown')
    x=inspect(p)['Selection_Context_v0_8']
    assert x['status']=='CONTEXT_UNKNOWN'
    assert x['probability_adjustment'] is False


def test_postcutoff_context_refused():
    p=pkt();p['competition_context']=context(stamp='2026-11-04T13:00:00+08:00')
    with pytest.raises(ValueError,match='post-cutoff'):
        inspect(p)


@pytest.mark.parametrize('update',[
    {'competition_context':{'source_id':'x','competition_kind':'friendly'}},
    {'competition_context':context('other')},
    {'competition_context':context(substitutions=5.5)},
    {'competition_context':dict(context(),declared_winner='home')},
])
def test_invalid_context_fails_closed(update):
    p=pkt();p.update(update)
    with pytest.raises(ValueError): inspect(p)


@pytest.mark.parametrize('field', ['actual_score','actual_halftime','actual_wdl',
                                     'actual_jc','actual_htft','final_result','recap',
                                     'red_card','in_play_events'])
def test_replay_or_inplay_field_rejected(field):
    p=pkt();p[field]='2:1'
    with pytest.raises(ValueError,match='postmatch/replay-only'):
        inspect(p)


def test_recap_11_is_descriptive_only_and_metrics_match_chat():
    file=Path(__file__).with_name('RECAP_20261113_11_MATCHES_CONVERSATION_ONLY.json')
    a=audit_recap(json.loads(file.read_text(encoding='utf-8')))
    targets={'single_hit':7,'protection_hit':9,'jc_hit':3,'goal_top3_hit':7,
             'score_top3_hit':2,'score_top1_hit':0,'htft_top2_hit':6}
    assert all(a['metrics'][k]=={'hits':v,'n':11} for k,v in targets.items())
    assert a['actual_let_draw_matches']==['001','002','005','011']
    assert a['let_draw_predicted_count']==0
    assert a['line_is_independently_official_verified'] is False
    assert a['production_score_eligible'] is False
    assert a['training_or_calibration_performed'] is False


def test_recap_falsely_labelled_official_is_rejected():
    rows=json.loads(Path(__file__).with_name('RECAP_20261113_11_MATCHES_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    rows['provenance']='OFFICIAL_FROZEN'
    with pytest.raises(ValueError,match='conversation recap'):
        audit_recap(rows)


def test_recap_duplicate_match_invalid():
    rows=json.loads(Path(__file__).with_name('RECAP_20261113_11_MATCHES_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    rows['matches'][1]['id']='001'
    with pytest.raises(ValueError,match='duplicate'):
        audit_recap(rows)
