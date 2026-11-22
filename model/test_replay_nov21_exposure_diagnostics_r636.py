"""Synthetic contracts for archived snapshot QA, NOT an accuracy backtest."""
import copy
import pytest
from replay_nov21_exposure_diagnostics_r636 import run,digest,neutral_htft


def dataset():
    q=[[0.]*18 for i in range(18)]
    for (h,a),v in { (0,0):.1,(1,0):.2,(2,0):.3,(2,1):.2,(3,0):.2 }.items():
        q[h][a]=v
    matches=[]
    for i in range(18):
        matches.append(dict(id=f'{i+5:03d}',league='test',
            match_local_time_beijing='2026-11-21T20:30:00+08:00',
            home='H',away='A',official_jc_signed_line=-1,
            regular_sp_prices=[1.3,4.1,6.0],handicap_sp_prices=[2.,3.,3.],
            market_implied_wdl={'胜':.8,'平':.1,'负':.1},
            market_implied_jc={'让胜':.5,'让平':.4,'让负':.1},
            score_probability_grid_18x18=copy.deepcopy(q),
            main_selection_research='胜',protect_selection_research='胜平',
            jc_selection_research='让胜',jc_protect_research='让胜/让平',
            goal_top3='3/2/1',score_top3='2:0/1:0/2:1',
            htft_candidates='胜胜/平胜',research_only=True))
    s=dict(schema='M79_SHADOW_20261121_MARKET_POISSON_PREMATCH_RESEARCH_V1',
           created_at_beijing='2026-11-21T17:12:11+08:00',fixture_sale_date='2026-11-21',
           source_url='example',source_capture_method='offline',
           source_snapshot_third_party_timestamp_verified=False,
           market_betting_availability_to_check_at_checkout=True,
           model='synthetic',model_prior_validated=False,
           full_M79_production_recreated=False,formal_grant=None,
           frozen_after_development_of_model=True,matches=matches)
    s['snapshot_sha256']=digest(s)
    return s


def test_synthetic_18_snapshot_replay_invariant_no_results():
    s=dataset();old=copy.deepcopy(s)
    out=run(s)
    assert s==old
    assert out['n_prematch']==18
    assert out['forward_validation_of_nov22_new_model'] is False
    assert out['count_gates']=={'Outcome':18,'JC':18,'Goal':18,'Score':18,'HTFT':18}
    assert out['formal_grant'] is None
    assert out['batch_prematch_exposure']['htft_proper_probabilities_available_n']==18


def test_snapshot_sha_tampering_blocks():
    s=dataset();s['matches'][0]['main_selection_research']='负'
    with pytest.raises(ValueError,match='sha256'):
        run(s)


def test_recognize_reforged_result_keys_even_if_digest_updated():
    s=dataset();s['matches'][0]['actual_score']='1:0'
    s['snapshot_sha256']=digest({k:v for k,v in s.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError,match='postmatch contamination'):
        run(s)


def test_suspicious_top_level_field_blocks():
    s=dataset();s['actual_winner']='胜'
    with pytest.raises(ValueError,match='top-level'):
        run(s)


def test_postmatch_unmatched_ids_fail():
    s=dataset();post={'schema':'NOV21_PREMATCH_FROZEN_VS_POSTMATCH_AUDIT',
       'snapshot_sha256_stored':s['snapshot_sha256'],'sha256_matches':True,
       'rows':[{'id':f'{i+6:03d}'} for i in range(18)]}
    with pytest.raises(ValueError,match='cohort'):
        run(s,post)