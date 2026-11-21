import copy
import pytest
from matchday_publish_gate_r636 import review, batch_concentration, published_only_bias, WDL, HTFT

T='2026-11-21T18:30:00+08:00'
C='2026-11-21T17:30:00+08:00'
O='2026-11-21T17:00:00+08:00'
Q=[{'score':'0:0','probability':.1},{'score':'1:0','probability':.2},
   {'score':'2:0','probability':.3},{'score':'2:1','probability':.2},
   {'score':'3:0','probability':.2}]

def pkt(i='001'):
    return dict(match_id=i,cutoff=C,kickoff=T,
        q_observation={'source_id':'archive-A','observed_at':O},score_grid=copy.deepcopy(Q),
        frozen_wdl='胜',published_score_top3=['2:0','1:0','2:1'],
        published_goal_top3=['2','3','1'],published_htft=['平胜','胜胜'],
        htft_probabilities=None,official_jc_line=-1,
        jc_observation={'source_id':'lottery-official','observed_at':O},
        evidence=[],market_home_buy_share=.85,
        publication_observation={'source_id':'original-publication','observed_at':O},
        market_buy_observation={'source_id':'public-buys','observed_at':O},
        reversal_proposal=None,reversal_policy=None)

def test_exact_margin_1_and_2_and_tail_are_all_from_q():
    r=review(pkt())
    assert r['wdl']==pytest.approx({'胜':.9,'平':.1,'负':0.})
    assert r['jc']==pytest.approx({'让胜':.5,'让平':.4,'让负':.1})
    assert r['margin_plus_one']==pytest.approx(.4)
    assert r['margin_plus_two']==pytest.approx(.3)
    assert r['goal_buckets']['1']==pytest.approx(.2)
    assert r['goal_buckets']['2']==pytest.approx(.3)
    assert r['goal_buckets']['3']==pytest.approx(.4)
    assert r['goal_buckets']['0']==pytest.approx(.1)
    assert r['formal_grant'] is None and not r['production_mutated']

def test_top3_discrepancy_is_a_warning_not_a_forced_change():
    x=pkt();x['published_score_top3']=['3:0','1:0','2:1']
    x['published_goal_top3']=['1','2','3']
    a=review(x)
    assert 'PUBLISHED_SCORE_TOP3_DIFFERS_FROM_FROZEN_Q' in a['warnings']
    assert 'PUBLISHED_GOAL_TOP3_DIFFERS_FROM_FROZEN_Q' in a['warnings']
    assert a['score_top3_derived']==['2:0','1:0','2:1']


def test_htft_fulltime_coherence_and_rank_check():
    x=pkt();x['htft_probabilities']={k:0. for k in HTFT}
    x['htft_probabilities'].update({'胜胜':.6,'平胜':.3,'平平':.1})
    x['published_htft']=['平胜','胜胜']
    r=review(x)
    assert r['htft_status']=='Q_MARGINALS_MATCHED_SHADOW_ONLY'
    assert 'PUBLISHED_HTFT_TOP2_NOT_PROBABILITY_RANKED' in r['warnings']
    x['htft_probabilities']['胜胜']-=.01
    x['htft_probabilities']['平平']+=.01
    with pytest.raises(ValueError,match='HTFT FT marginal'):
        review(x)


def test_market_only_cannot_reverse():
    x=pkt(); x['reversal_proposal']='平'
    x['evidence']=[{'family':'market','impact':'adverse','source_id':f'm{i}','observed_at':O} for i in range(4)]
    x['reversal_policy']={'source_id':'preregistered','registered_at':'2026-11-20T12:00:00+08:00','minimum_gap':0.}
    assert not review(x)['reversal_review_eligible']
    x['evidence']+=[{'family':'roster','impact':'adverse','source_id':'r1','observed_at':O},
                    {'family':'schedule','impact':'adverse','source_id':'s1','observed_at':O}]
    # Research reviewer gate still refuses if suggested direction lacks Q gap
    assert not review(x)['reversal_review_eligible']


def test_reversal_only_possible_for_2_families_with_registered_policy_and_edge():
    x=pkt();x['frozen_wdl']='平';x['reversal_proposal']='胜'
    x['evidence']=[{'family':f,'impact':'adverse','source_id':f,'observed_at':O} for f in ('roster','schedule')]
    x['reversal_policy']={'source_id':'preregistered','registered_at':'2026-11-20T12:00:00+08:00','minimum_gap':.3}
    assert review(x)['reversal_review_eligible']
    x['reversal_policy']['registered_at']='2026-11-22T00:00:00+08:00'
    assert not review(x)['reversal_review_eligible']
    assert review(x)['formal_grant'] is None


def test_all_home_and_htft_concentration_only_warn():
    x=[review(pkt(f'{i:03d}')) for i in range(8)]
    b=batch_concentration(x,published_htft=['平胜']*6+['胜胜']*2)
    assert b['wdl_counts']=={'胜':8,'平':0,'负':0}
    assert b['wdl_hhi']==pytest.approx(1.)
    assert len(b['flags'])==2 and not b['change_any_pick']


def test_leakage_never_enters_aic_or_odds():
    x=pkt();x['actual_half_time_score']='0:0'
    with pytest.raises(ValueError,match='unexpected'):
        review(x)
    x=pkt();x['evidence']=[{'family':'roster','impact':'adverse','source_id':'new-injury','observed_at':T}]
    with pytest.raises(ValueError,match='postcutoff'):
        review(x)
    x=pkt();x['q_observation']['observed_at']=T
    with pytest.raises(ValueError,match='postcutoff'):
        review(x)


def test_incomplete_q_or_invalid_line_block_and_no_timezone():
    x=pkt();x['score_grid']=x['score_grid'][:3]
    with pytest.raises(ValueError,match='tail mass'):
        review(x)
    x=pkt();x['official_jc_line']=-.75
    with pytest.raises(ValueError,match='INTEGER'):
        review(x)
    x=pkt();x['q_observation']['observed_at']='2026-11-21T17:00:00'
    with pytest.raises(ValueError,match='naive'):
        review(x)


def test_missing_jc_is_explicit_not_assumed():
    x=pkt();x['official_jc_line']=None;x['jc_observation']=None
    o=review(x)
    assert o['jc'] is None and o['official_jc_line'] is None


def test_batch_duplicate_match_block():
    x=review(pkt())
    with pytest.raises(ValueError,match='duplicate'):
        batch_concentration([x,x])


def test_published_only_yesterday_benchmark_does_not_claim_q():
    records = [dict(match_id=f'{i:03d}', ordinary_offered=(i!=6), frozen_wdl='胜',
                   htft_primary='胜胜' if i in (2,6) else '平胜') for i in range(1,9)]
    out=published_only_bias(records)
    assert out['ordinary_offered_n']==7
    assert out['formal_wdl_counts']=={'胜':7,'平':0,'负':0}
    assert out['htft_primary_counts']['平胜']==6
    assert out['htft_primary_counts']['胜胜']==2
    assert out['no_joint_q_claim'] and out['automatic_pick_changes'] is False
    assert len(out['warnings'])==2

def test_buy_share_needs_precutoff_source():
    x=pkt();x['market_buy_observation']['observed_at']=T
    with pytest.raises(ValueError,match='postcutoff'):
        review(x)

def test_two_families_one_same_news_source_not_independent():
    x=pkt();x['frozen_wdl']='平';x['reversal_proposal']='胜'
    x['reversal_policy']={'source_id':'registered','registered_at':'2026-11-20T10:00:00+08:00','minimum_gap':.1}
    x['evidence']=[{'family':fam,'impact':'adverse','source_id':'same-post','observed_at':O} for fam in ('roster','tactics')]
    assert review(x)['reversal_review_eligible'] is False


def test_aic_expected_role_and_replacement_uncertainty_no_adjust():
    from matchday_publish_gate_r636 import audit_aic_availability
    rec={"player_id":"keeper1","role":"GK","availability_state":"out","expected_minutes":0,
         "replacement_id":"center-back1","replacement_role":"CB",
         "source_id":"team-press","observed_at":O}
    r=audit_aic_availability([rec],cutoff=C,kickoff=T)
    assert r['numeric_xg_delta'] is None
    assert r['issues'][0]['flag']=='POSITION_ROLE_MISMATCH_REVIEW_ONLY'
    rec['observed_at']=T
    with pytest.raises(ValueError,match='postcutoff'):
        audit_aic_availability([rec],cutoff=C,kickoff=T)


def test_aic_rejects_actual_subs_and_duplicate_same_player():
    from matchday_publish_gate_r636 import audit_aic_availability
    rec={"player_id":"striker","role":"ST","availability_state":"out","expected_minutes":0,
         "replacement_id":None,"replacement_role":None,"source_id":"team-press","observed_at":O}
    assert audit_aic_availability([rec],cutoff=C,kickoff=T)['issues'][0]['flag']=='REPLACEMENT_UNCONFIRMED_NO_NUMERIC_EFFECT'
    with pytest.raises(ValueError,match='duplicate'):
        audit_aic_availability([rec,rec],cutoff=C,kickoff=T)
    with pytest.raises(ValueError,match='schema'):
        audit_aic_availability([{**rec,'actual_substitution_minute':60}],cutoff=C,kickoff=T)


def test_development_casebook_replay_equal_prior_published_scoring():
    import json
    from pathlib import Path
    from replay_published_dev_20261121 import replay
    d=json.loads(Path(__file__).with_name('DEV_ONLY_CASEBOOK_20261120_8.json').read_text(encoding='utf-8'))
    r=replay(d)
    assert r['stats']=={'ordinary_n':7,'wdl_single':3,'wdl_protection':4,
                        'goal_top3':3,'goal_top2':3,'score_top3':0,
                        'jc':3,'htft_main':1,'htft_top2':1}
    assert r['concentration']['warnings']==[
        'ORDINARY_HOME_SINGLE_OVERCONCENTRATED',
        'HTFT_HOME_FINISH_OVERCONCENTRATED']
    assert r['formal_grant'] is None and not r['comparable_new_model_probabilities']
