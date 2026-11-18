import copy
import pytest
from shadow_r638 import inspect
from test_shadow_r637 import coherent_packet
from test_motivation_squad_r634 import pkt, BEFORE


def snap(kind, prefix, at=BEFORE):
    basis={"reference":"last_league_xi","projected":"precutoff_projected_xi","official":"official_starting_xi"}[kind]
    return {"basis":basis,"source_id":f"{kind}-{prefix}","observed_at":at,"player_ids":[f"{prefix}{i}" for i in range(11)]}


def test_immutable_no_probability_fit_and_no_grants():
    p=pkt(); old=copy.deepcopy(p)
    out=inspect(p)
    assert p==old
    assert out["outcome_probabilities_unchanged"]==[.46,.27,.27]
    assert out["version"].endswith("R6.3.8_20261112")
    assert all(out[k] is None for k in ("formal_single_grant","formal_core_grant","formal_protection_grant","formal_handicap_grant"))
    assert out["production_changed"] is False
    assert out["Selection_Efficiency_v0_6"]["raw_direction"] == "胜"


def test_heavy_rotation_research_hold_no_direction_flip():
    p=pkt(p=(.70,.15,.15),research_selection_level="core_candidate")
    p["lineup_snapshots"]={"home":{"reference":snap("reference","old"),
        "projected":snap("projected","new"),"official":snap("official","new")}}
    o=inspect(p)
    x=o["LCRG_v0_1_lineup_rotation_review"]
    assert x["side_audits"]["home"]["reference_rotation_count"] == 11
    assert x["side_audits"]["home"]["projected_surprise_count"] == 0
    assert x["extra_core_hold"] is True
    assert x["independent_risk_families_added"] == 0
    assert o["Selection_Efficiency_v0_6"]["raw_direction"]=="胜"
    assert o["outcome_probabilities_unchanged"]==[.70,.15,.15]


def test_large_projected_surprise_flags_even_without_reference():
    p=pkt()
    p["lineup_snapshots"]={"home":{"projected":snap("projected","old"),"official":snap("official","new")}}
    a=inspect(p)["LCRG_v0_1_lineup_rotation_review"]
    assert a["selected_side_review"]=="HOLD_CORE_LARGE_PROJECTED_LINEUP_SURPRISE"


def test_undocumented_or_postcutoff_lineup_fails_closed():
    p=pkt(); p["lineup_snapshots"]={"home":{"official":snap("official","new", "2026-11-04T13:00:00+08:00")}}
    with pytest.raises(ValueError,match="post-cutoff"): inspect(p)
    p=pkt(); p["lineup_snapshots"]={"home":{"official":snap("official","new")}}
    p["lineup_snapshots"]["home"]["official"]["player_ids"][0]="new1"
    with pytest.raises(ValueError,match="distinct"): inspect(p)


def test_predicted_reference_cannot_postdate_official():
    p=pkt(); p["lineup_snapshots"]={"home":{"reference":snap("reference","old", "2026-11-04T10:00:00+08:00"),
        "official":snap("official","new", "2026-11-04T09:00:00+08:00")}}
    with pytest.raises(ValueError,match="cannot postdate"): inspect(p)


def test_halfgoal_asian_substitution_rejected_by_inherited_contract():
    p=coherent_packet(official_handicap_line=-1.5,
        official_handicap_line_source={"basis":"official_jc_handicap","source_id":"bad","observed_at":BEFORE}, frozen_handicap_pick="让平")
    with pytest.raises(ValueError, match="integer"): inspect(p)


def test_let_draw_exact_margin_is_same_matrix_mass_for_minus1():
    p=coherent_packet(official_handicap_line=-1,
        official_handicap_line_source={"basis":"official_jc_handicap","source_id":"JC","observed_at":BEFORE},frozen_handicap_pick="让负")
    o=inspect(p)
    m=o["S4_v1_8_exact_margin_exposure"]
    assert m["status"] == "EXACT_JC_MARGIN_AUDITED"
    assert m["required_home_minus_away_margin"] == 1
    assert m["p_exact_margin_let_draw"] == pytest.approx(.10)
    assert m["one_goal_let_draw_case"] is True
    assert m["frozen_pick_unchanged"] == "让负"


def test_let_draw_exact_margin_is_away_win_by_one_for_plus1():
    p=coherent_packet(official_handicap_line=1,
        official_handicap_line_source={"basis":"official_jc_handicap","source_id":"JC","observed_at":BEFORE},frozen_handicap_pick="让胜")
    m=inspect(p)["S4_v1_8_exact_margin_exposure"]
    assert m["p_exact_margin_let_draw"] == pytest.approx(.08)
    assert m["required_home_minus_away_margin"] == -1


def test_low_high_tails_are_observation_not_forced_goal_top3():
    p=coherent_packet()
    o=inspect(p)["RC2_6_low_high_tail_integrity"]
    assert o["p_1"] == pytest.approx(.18)
    assert o["p_7plus_aggregate"] == pytest.approx(.05)
    assert "7+" not in o["exact_0_to_6_rank_watch"]
    assert o["seven_plus_is_aggregate_not_exact_integer"] is True
    assert o["no_new_tail_slots"] is True


@pytest.mark.parametrize("forbidden",["actual_score","red_card","in_play_events","final_score"])
def test_postmatch_or_inplay_keys_never_enter_prematch(forbidden):
    p=pkt(); p[forbidden]=[1,2]
    with pytest.raises(ValueError,match="postmatch or in-play"): inspect(p)


def test_unknown_lineup_cannot_raise_a_false_safe_grant():
    a=inspect(pkt())["LCRG_v0_1_lineup_rotation_review"]
    assert a["status"].startswith("UNKNOWN")
    assert a["extra_core_hold"] is False
