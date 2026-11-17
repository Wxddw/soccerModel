import copy
import json
from pathlib import Path
import pytest
from shadow_r636 import inspect, replay_batch14
from test_motivation_squad_r634 import pkt, BEFORE


def coherent_matrix():
    rows = [
        ('0:0', .10), ('1:1', .10), ('2:2', .10),
        ('1:0', .10), ('2:0', .20), ('3:1', .10), ('4:0', .10),
        ('0:1', .10), ('0:2', .10),
    ]
    return [{'score':s,'probability':p} for s,p in rows]


def coherent_packet(**kw):
    p = pkt(p=(.50,.30,.20))
    p['score_matrix'] = coherent_matrix()
    p['goal_distribution'] = {'0':.10,'1':.20,'2':.40,'3':0.0,'4':.30,'5':0.0,'6':0.0,'7+':0.0}
    p.update(kw)
    return p


def ev(family, bucket):
    return {'family':family,'bucket':bucket,'source_id':f'{family}-{bucket}','observed_at':BEFORE}


def test_r636_keeps_production_and_probabilities_unchanged():
    p = pkt(); frozen = copy.deepcopy(p)
    out = inspect(p)
    assert p == frozen
    assert out['version'].endswith('R6.3.6_20261108')
    assert out['outcome_probabilities_unchanged'] == [.46,.27,.27]
    assert out['probability_adjustment_applied'] is False
    assert out['automatic_direction_flip'] is False
    assert out['formal_single_grant'] is None
    assert out['formal_core_grant'] is None
    assert out['formal_protection_grant'] is None
    assert out['formal_handicap_grant'] is None
    assert out['production_changed'] is False


def test_protection_tie_without_prior_pair_is_not_released():
    out = inspect(pkt(p=(.40,.30,.30)))['Protection_v0_2']
    assert out['status'] == 'MANUAL_REVIEW_NO_PRIOR_PAIR'
    assert out['research_proposed_protection'] is None
    assert out['candidate_pair_for_manual_review'] == ['胜','平']
    assert out['formal_protection_grant'] is None


def test_protection_tie_preserves_prior_pair_for_manual_review():
    out = inspect(pkt(p=(.40,.30,.30), previous_research_protection=['胜','负']))['Protection_v0_2']
    assert out['status'] == 'MANUAL_REVIEW_KEEP_PRIOR_PAIR'
    assert out['candidate_pair_for_manual_review'] == ['胜','负']


def test_protection_rejects_prior_pair_without_raw_top1():
    with pytest.raises(ValueError, match='must include raw Top1'):
        inspect(pkt(p=(.40,.30,.30), previous_research_protection=['平','负']))


def test_draw_score_cluster_conflicts_with_protection_pair_and_only_flags():
    matrix = [
      {'score':'1:1','probability':.15}, {'score':'2:2','probability':.14}, {'score':'0:0','probability':.01},
      {'score':'1:0','probability':.11}, {'score':'2:0','probability':.10}, {'score':'2:1','probability':.10},
      {'score':'0:1','probability':.13}, {'score':'0:2','probability':.13}, {'score':'1:2','probability':.13}]
    p = pkt(p=(.31,.30,.39))
    p['score_matrix'] = matrix
    p['goal_distribution'] = {'0':.01,'1':.24,'2':.38,'3':.23,'4':.14,'5':0.0,'6':0.0,'7+':0.0}
    out = inspect(p)['Protection_v0_2']
    assert 'DRAW_SCORE_FAMILY_CONFLICTS_WITH_PROTECTION_PAIR' in out['cross_layer_flags']
    assert out['formal_protection_grant'] is None


def test_exact_zero_bucket_gets_one_tail_slot_with_two_independent_families():
    p = pkt()
    p['goal_distribution'] = {'0':.06,'1':.12,'2':.28,'3':.24,'4':.14,'5':.08,'6':.05,'7+':.03}
    p['exact_tail_evidence'] = [ev('pace_transition','0'),ev('market_ou','0')]
    out = inspect(p)['RC2_5_exact_bucket_router']
    assert out['status'] == 'EXACT_BUCKET_ONE_SLOT'
    assert out['exact_tail_bucket'] == '0'
    assert out['shadow_top3'][0] == '2' and '0' in out['shadow_top3']
    assert out['tail_slots_used'] == 1


def test_exact_five_bucket_gets_one_tail_slot():
    p = pkt()
    p['goal_distribution'] = {'0':.02,'1':.08,'2':.20,'3':.22,'4':.18,'5':.15,'6':.09,'7+':.06}
    p['exact_tail_evidence'] = [ev('attacking_profile','5'),ev('set_piece_profile','5')]
    out = inspect(p)['RC2_5_exact_bucket_router']
    assert out['status'] == 'EXACT_BUCKET_ONE_SLOT'
    assert out['exact_tail_bucket'] == '5'
    assert out['shadow_top3'][0] == '3' and '5' in out['shadow_top3']


def test_exact_zero_and_five_conflict_keeps_base():
    p = pkt()
    p['goal_distribution'] = {'0':.06,'1':.12,'2':.28,'3':.24,'4':.14,'5':.08,'6':.05,'7+':.03}
    p['exact_tail_evidence'] = [ev('pace_transition','0'),ev('market_ou','0'),ev('attacking_profile','5'),ev('set_piece_profile','5')]
    out = inspect(p)['RC2_5_exact_bucket_router']
    assert out['status'] == 'EXACT_TAIL_CONFLICT_KEEP_BASE'
    assert out['shadow_top3'] == out['base_top3']


def test_exact_tail_duplicate_family_across_broad_and_exact_routes_rejected():
    p = pkt()
    p['goal_distribution'] = {'0':.06,'1':.12,'2':.28,'3':.24,'4':.14,'5':.08,'6':.05,'7+':.03}
    p['tail_evidence'] = [{'family':'market_ou','direction':'low','source_id':'m','observed_at':BEFORE}]
    p['exact_tail_evidence'] = [ev('market_ou','0'),ev('pace_transition','0')]
    with pytest.raises(ValueError, match='counted more than once'):
        inspect(p)


def test_exact_tail_rejects_post_cutoff_evidence():
    p = pkt()
    p['goal_distribution'] = {'0':.06,'1':.12,'2':.28,'3':.24,'4':.14,'5':.08,'6':.05,'7+':.03}
    p['exact_tail_evidence'] = [ev('market_ou','0'),{**ev('pace_transition','0'),'observed_at':'2026-11-04T21:30:00+08:00'}]
    with pytest.raises(ValueError, match='post-cutoff'):
        inspect(p)


def test_exact_tail_requires_two_independent_families():
    p = pkt(); p['goal_distribution'] = {'0':.06,'1':.12,'2':.28,'3':.24,'4':.14,'5':.08,'6':.05,'7+':.03}
    p['exact_tail_evidence'] = [ev('market_ou','5')]
    out = inspect(p)['RC2_5_exact_bucket_router']
    assert out['status'] == 'NO_TWO_FAMILY_EXACT_BUCKET_TRIGGER'


def test_score_family_audit_keeps_original_top3_and_adds_family_candidates():
    p = coherent_packet()
    frozen = copy.deepcopy(p['score_matrix'])
    out = inspect(p)['GS1_4_score_family_audit']
    assert out['status'] == 'SCORE_FAMILY_AUDITED'
    assert len(out['score_top3']) == 3
    assert set(out['family_watch_candidates']) == {'胜','平','负'}
    assert out['ranking_changed'] is False
    assert p['score_matrix'] == frozen


def test_handicap_is_aggregated_from_joint_score_matrix():
    out = inspect(coherent_packet(home_handicap_line=-1))['S4_v1_6_joint_handicap_audit']
    assert out['status'] == 'JOINT_MATRIX_HANDICAP_AUDITED'
    assert out['handicap_probabilities']['让胜'] == .4
    assert out['handicap_probabilities']['让平'] == .1
    assert out['handicap_probabilities']['让负'] == .5
    assert out['research_top1'] == '让负'
    assert out['net_margin_probabilities']['home_margin_2plus'] == .4


def test_handicap_close_top_two_is_manual_review():
    p = coherent_packet(home_handicap_line=-1)
    # Rebuild a matrix where adjusted win/loss are tied to within 1pp, retaining WDL.
    p['score_matrix'] = [
      {'score':'2:0','probability':.35}, {'score':'1:0','probability':.35},
      {'score':'0:0','probability':.15}, {'score':'0:1','probability':.15}]
    p['probabilities'] = [.70,.15,.15]
    p['goal_distribution'] = {'0':.15,'1':.50,'2':.35,'3':0,'4':0,'5':0,'6':0,'7+':0}
    out = inspect(p)['S4_v1_6_joint_handicap_audit']
    assert out['status'] == 'MANUAL_REVIEW_CLOSE_HANDICAP_OUTCOMES'
    assert out['research_top1'] is None


def test_handicap_missing_matrix_or_line_is_unknown():
    p = pkt()
    assert inspect(p)['S4_v1_6_joint_handicap_audit']['status'] == 'UNKNOWN_NO_SCORE_MATRIX_OR_HANDICAP_LINE'


def test_avoidance_review_flags_opportunity_without_auto_restoring():
    p = pkt(p=(.399,.266,.335), research_selection_level='avoid')
    out = inspect(p)['Selection_Efficiency_v0_4']
    assert out['avoidance_recovery_review'] == 'REVIEW_AVOIDED_TOP1_OPPORTUNITY_NO_AUTO_RESTORE'
    assert out['raw_direction'] == '胜'
    assert out['formal_single_grant'] is None
    assert out['automatic_direction_flip'] is False


def test_high_risk_hfrg_prevents_avoidance_recovery_prompt():
    risk = [
      {'family':'roster','state':'adverse_to_home','source_id':'r','observed_at':BEFORE,'critical_spine_severe':True}]
    p = pkt(p=(.51,.45,.04), research_selection_level='avoid', risk_evidence=risk)
    out = inspect(p)['Selection_Efficiency_v0_4']
    assert out['avoidance_recovery_review'] == 'KEEP_HOLD_HIGH_RISK_NOT_RECOVERY'


def test_half_full_top2_not_released_without_joint_distribution():
    out = inspect(pkt())['HT_State_v0_3']
    assert out['top2'] is None
    assert out['top2_release_status'] == 'NO_TOP2_RELEASE_MISSING_JOINT_MATRIX'
    assert out['fallback_from_score_top3_forbidden'] is True


def test_inspect_rejects_post_match_fields():
    p = pkt(); p['actual_score'] = [2,1]
    with pytest.raises(ValueError, match='post-match field not allowed'):
        inspect(p)


def test_batch14_recap_arithmetic_is_descriptive_only():
    rows = json.loads(Path(__file__).with_name('RECAP_14_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    out = replay_batch14(rows)
    assert out['n'] == 14
    assert out['metrics']['single']['hits'] == 9
    assert out['metrics']['protection']['hits'] == 10
    assert out['metrics']['handicap']['hits'] == 7
    assert out['metrics']['goals_top3']['hits'] == 9
    assert out['metrics']['score_top3']['hits'] == 4
    assert out['metrics']['half_full_top2']['hits'] == 5
    assert out['correct_top1_in_avoidance_groups'] == 3
    assert out['avoidance_group_n'] == 3
    assert out['independent_validation'] is False
    assert out['training_or_threshold_fit'] is False


def test_batch14_replay_rejects_duplicate_rows():
    rows = json.loads(Path(__file__).with_name('RECAP_14_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    with pytest.raises(ValueError, match='unique id'):
        replay_batch14(rows + [rows[0]])


def test_clear_protection_rank_order_releases_shadow_candidate_not_formal_grant():
    out = inspect(pkt(p=(.46,.31,.23)))['Protection_v0_2']
    assert out['status'] == 'CLEAR_RANK_ORDER_SHADOW_ONLY'
    assert out['research_proposed_protection'] == ['胜','平']
    assert out['formal_protection_grant'] is None


def test_replay_rejects_protection_that_excludes_raw_top1():
    rows = json.loads(Path(__file__).with_name('RECAP_14_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    rows[0]['protection'] = ['平','负']
    with pytest.raises(ValueError, match='must include the raw unique direction'):
        replay_batch14(rows)
