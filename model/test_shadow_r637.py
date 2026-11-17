import copy, json
from pathlib import Path
import pytest
from shadow_r637 import inspect, replay_conversation_recap25
from test_motivation_squad_r634 import pkt, BEFORE, squads, motivation


def fav_ev(family, state='neutral', severe=False, stamp=BEFORE):
    return {'family':family,'state':state,'critical_spine_severe':severe,
            'source_id':f'{family}-source','observed_at':stamp}


def coherent_packet(**kw):
    p=pkt(p=(.50,.30,.20))
    p['score_matrix']=[
        {'score':'0:0','probability':.05}, {'score':'1:1','probability':.10}, {'score':'2:2','probability':.15},
        {'score':'1:0','probability':.10}, {'score':'2:0','probability':.20}, {'score':'3:1','probability':.10}, {'score':'4:0','probability':.10},
        {'score':'0:1','probability':.08}, {'score':'0:2','probability':.07}, {'score':'0:7','probability':.05}]
    p['goal_distribution']={'0':.05,'1':.18,'2':.37,'3':.0,'4':.35,'5':.0,'6':.0,'7+':.05}
    p.update(kw)
    return p


def test_r637_preserves_production_probabilities_and_all_formal_grants_null():
    p=pkt(); frozen=copy.deepcopy(p); out=inspect(p)
    assert p==frozen
    assert out['version'].endswith('R6.3.7_20261109')
    assert out['outcome_probabilities_unchanged']==[.46,.27,.27]
    assert out['probability_adjustment_applied'] is False
    assert out['automatic_direction_flip'] is False
    assert out['formal_single_grant'] is None
    assert out['formal_core_grant'] is None
    assert out['formal_protection_grant'] is None
    assert out['formal_handicap_grant'] is None
    assert out['production_changed'] is False


def test_away_favorite_without_directional_evidence_holds_core_only_not_single():
    p=pkt(p=(.20,.20,.60),research_selection_level='core_candidate')
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='UNKNOWN_INSUFFICIENT_DIRECTIONAL_EVIDENCE'
    assert out['Selection_Efficiency_v0_5']['raw_direction']=='负'
    assert out['Selection_Efficiency_v0_5']['core_candidate_review']=='HOLD_CORE_EVIDENCE_INCOMPLETE'
    assert out['Selection_Efficiency_v0_5']['single_direction_retained']=='负'
    assert out['formal_single_grant'] is None


def test_away_favorite_two_adverse_independent_families_high_risk():
    p=pkt(p=(.20,.20,.60),research_selection_level='core_candidate')
    p['favorite_risk_evidence']=[fav_ev('roster','adverse_to_favorite',True),fav_ev('tactical','adverse_to_favorite')]
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='HIGH_RISK_CRITICAL_ROSTER_TO_RAW_DIRECTION'
    assert out['Selection_Efficiency_v0_5']['core_candidate_review']=='HOLD_CORE_HIGH_RISK'
    assert out['outcome_probabilities_unchanged']==[.20,.20,.60]


def test_away_favorite_two_adverse_families_without_critical_flag():
    p=pkt(p=(.20,.20,.60))
    p['favorite_risk_evidence']=[fav_ev('schedule','adverse_to_favorite'),fav_ev('opponent_strength','adverse_to_favorite')]
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='HIGH_RISK_TWO_INDEPENDENT_FAMILIES'


def test_two_families_without_adverse_clear_directional_core_gate():
    m=motivation(home_urg='low',away_urg='high',home_must=False,away_must=True)
    m['away']['stakes_type']='title'
    p=pkt(p=(.12,.14,.74),research_selection_level='core_candidate',motivation=m,evidence=[
      {'family':'official_lineup','source_id':'xi','observed_at':BEFORE,'state':'favorable'},
      {'family':'market_price','source_id':'market','observed_at':BEFORE,'state':'favorable'}])
    p['favorite_risk_evidence']=[fav_ev('roster','favorable_to_favorite'),fav_ev('tactical','neutral')]
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='REVIEWED_NO_ADVERSE_FAMILY'
    assert out['Selection_Efficiency_v0_5']['core_candidate_review']=='RESEARCH_CORE_REVIEW_READY_NOT_GRANTED'
    assert out['formal_core_grant'] is None


def test_legacy_home_relative_risk_is_inverted_for_away_direction():
    p=pkt(p=(.20,.20,.60))
    p['risk_evidence']=[
      {'family':'roster','source_id':'r','observed_at':BEFORE,'state':'favorable_to_home'},
      {'family':'tactical_matchup','source_id':'t','observed_at':BEFORE,'state':'favorable_to_home'}]
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='HIGH_RISK_TWO_INDEPENDENT_FAMILIES'
    assert out['DVRG_v0_1']['independent_families']['roster']['state']=='adverse_to_favorite'


def test_esr_role_functionality_is_one_roster_family_and_flags_away_keeper_drop():
    p=pkt(p=(.20,.20,.60),squads=squads(away_keeper_change=-33))
    out=inspect(p)
    f=out['ESR_Functionality_v0_1']
    assert f['status']=='CONFIRMED_BOTH'
    assert 'RAW_DIRECTION_GOALKEEPER_REPLACEMENT_QUALITY_DROP' in f['flags']
    assert out['DVRG_v0_1']['family_count']==1
    assert out['DVRG_v0_1']['critical_roster_risk'] is True


def test_msi_opponent_pressure_is_context_not_an_independent_risk_vote():
    m=motivation(home_urg='low',away_urg='high',home_must=False,away_must=True)
    m['away']['stakes_type']='title'
    p=pkt(p=(.60,.20,.20),motivation=m,squads=None)
    p['favorite_risk_evidence']=[fav_ev('market','neutral')]
    out=inspect(p)
    assert 'OPPONENT_OBJECTIVE_STAKES_EDGE_REVIEW' in out['DVRG_v0_1']['motivation_context_flags']
    assert out['DVRG_v0_1']['family_count']==1
    assert out['DVRG_v0_1']['status']=='UNKNOWN_INSUFFICIENT_DIRECTIONAL_EVIDENCE'
    assert out['outcome_probabilities_unchanged']==[.60,.20,.20]


def test_favorite_evidence_rejects_post_cutoff_record():
    p=pkt(p=(.20,.20,.60))
    p['favorite_risk_evidence']=[fav_ev('roster','neutral',stamp='2026-11-04T13:00:00+08:00')]
    with pytest.raises(ValueError,match='post-cutoff'):
        inspect(p)


def test_gs15_adds_draw_runner_up_and_total_bucket_candidates_without_reordering():
    p=coherent_packet()
    out=inspect(p)['GS1_5_score_family_runner_up_audit']
    assert out['status']=='SCORE_FAMILY_RUNNER_UP_AUDITED'
    assert out['score_top3_unchanged'] is True
    assert out['score_top3']==['2:0','2:2','1:0']
    assert [x['score'] for x in out['result_family_top2']['平']]==['2:2','1:1']
    assert out['draw_multi_goal_watch'][0]['score']=='2:2'
    assert out['probability_adjustment'] is False


def test_s4_v17_requires_official_integer_line_and_frozen_pick():
    out=inspect(pkt())['S4_v1_7_official_handicap_contract']
    assert out['status']=='UNKNOWN_MISSING_OFFICIAL_INTEGER_LINE_SOURCE_OR_FROZEN_PICK'
    assert out['asian_handicap_substitution_forbidden'] is True
    assert out['accuracy_scored'] is False


def test_s4_v17_accepts_only_timestamped_official_jc_line():
    p=coherent_packet(official_handicap_line=-1,
      official_handicap_line_source={'source_id':'official-jc','observed_at':BEFORE,'basis':'official_jc_handicap'},
      frozen_handicap_pick='让负')
    out=inspect(p)['S4_v1_7_official_handicap_contract']
    assert out['status']=='JOINT_MATRIX_HANDICAP_AUDITED'
    assert out['official_handicap_line']==-1
    assert out['frozen_handicap_pick']=='让负'
    assert out['accuracy_scored'] is False


def test_s4_v17_rejects_line_conflict_and_asian_substitution():
    p=coherent_packet(home_handicap_line=-1,official_handicap_line=1,
      official_handicap_line_source={'source_id':'official-jc','observed_at':BEFORE,'basis':'official_jc_handicap'},
      frozen_handicap_pick='让胜')
    with pytest.raises(ValueError,match='conflicts'):
        inspect(p)


def test_r636_exact_tail_branch_bug_fixed_in_r637_package():
    p=coherent_packet()
    p['exact_tail_evidence']=[
      {'family':'pace_transition','bucket':'7+','source_id':'pace','observed_at':BEFORE},
      {'family':'set_piece_profile','bucket':'7+','source_id':'setpiece','observed_at':BEFORE}]
    out=inspect(p)
    assert out['GS1_4_score_family_audit']['status']=='SCORE_FAMILY_AUDITED'
    assert 'EXACT_TAIL_GOAL_BUCKET_NOT_REPRESENTED_IN_SCORE_TOP3' in out['GS1_4_score_family_audit']['flags']


def test_recap25_metrics_recomputed_and_half_full_corrected():
    rows=json.loads(Path(__file__).with_name('RECAP_25_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    out=replay_conversation_recap25(rows)
    assert out['n']==25
    assert out['metrics']['single']['hits']==16
    assert out['metrics']['protection']['hits']==22
    assert out['metrics']['goals_top3']['hits']==20
    assert out['metrics']['score_top3']['hits']==17
    assert out['metrics']['half_full_top2']['hits']==16
    assert out['handicap_metric'] is None
    assert out['independent_validation'] is False
    assert out['training_or_threshold_fit'] is False


def test_recap25_rejects_duplicate_ids_and_protection_excluding_single():
    rows=json.loads(Path(__file__).with_name('RECAP_25_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    rows[-1]=copy.deepcopy(rows[0])
    with pytest.raises(ValueError,match='unique string id'):
        replay_conversation_recap25(rows)
    rows=json.loads(Path(__file__).with_name('RECAP_25_INPUT_CONVERSATION_ONLY.json').read_text(encoding='utf-8'))
    rows[0]['protection']=['平','负']
    with pytest.raises(ValueError,match='must contain the unique single'):
        replay_conversation_recap25(rows)


def test_esr_critical_role_drop_cannot_be_overridden_by_favorable_roster_text():
    p=pkt(p=(.20,.20,.60),squads=squads(away_keeper_change=-33))
    p['favorite_risk_evidence']=[fav_ev('roster','favorable_to_favorite'),fav_ev('tactical','neutral')]
    out=inspect(p)
    assert out['DVRG_v0_1']['status']=='HIGH_RISK_CRITICAL_ROSTER_TO_RAW_DIRECTION'
    assert out['DVRG_v0_1']['family_count']==2
    assert out['DVRG_v0_1']['independent_families']['roster']['state']=='adverse_to_favorite'
    assert 'ESR_same_roster_family' in out['DVRG_v0_1']['independent_families']['roster']['origin']
