import copy
import pytest

from shadow_r639 import inspect
from replay_conversation_r639 import audit_recap
from test_shadow_r637 import coherent_packet
from test_shadow_r638 import snap
from test_motivation_squad_r634 import pkt, BEFORE

JC_SOURCE={"basis":"official_jc_handicap", "source_id":"jc-official", "observed_at":BEFORE}


def jc_pkt(line=-1,pick="让负"):
    return coherent_packet(official_handicap_line=line,
                           official_handicap_line_source=JC_SOURCE.copy(),
                           frozen_handicap_pick=pick)


def event(kind="squad_return", side="home", player="n0", stamp=BEFORE):
    return {"kind":kind, "side":side, "player_id":player,
            "observed_at":stamp,"source_id":"team-report"}


def test_research_only_immutability_of_parent_and_packet():
    p=jc_pkt(); frozen=copy.deepcopy(p)
    out=inspect(p)
    assert frozen==p
    assert out["outcome_probabilities_unchanged"]==[.5,.3,.2]
    assert out["version"].endswith("R6.3.9_20261113")
    assert out["production_changed"] is False
    assert out["probability_adjustment_applied"] is False
    assert out["automatic_direction_flip"] is False
    assert all(out[k] is None for k in ("formal_single_grant","formal_core_grant",
                                       "formal_protection_grant","formal_handicap_grant"))


def test_close_three_way_002_is_manual_review_not_draw_auto_select():
    p=pkt(p=(.330,.313,.357))
    o=inspect(p)
    x=o["Protection_v0_3_ambiguity_review"]
    assert x["three_way_cluster"] is True
    assert x["raw_direction_unchanged"]=="负"
    assert x["research_candidate_pair_unchanged"]==["负","胜"]
    assert x["candidate_release_for_research"] is False
    assert x["draw_excluded_near_runner_up"] is True
    assert o["Selection_Efficiency_v0_7"]["raw_direction"]=="负"
    assert o["outcome_probabilities_unchanged"]==[.330,.313,.357]


def test_three_way_cluster_without_draw_exclusion_is_still_manual_review():
    p=pkt(p=(.334,.335,.331))
    x=inspect(p)["Protection_v0_3_ambiguity_review"]
    assert x["three_way_cluster"] is True
    assert x["draw_excluded_near_runner_up"] is False
    assert x["candidate_release_for_research"] is False


def test_well_separated_outcome_keeps_research_candidate_but_no_formal_grant():
    x=inspect(pkt(p=(.7,.2,.1)))["Protection_v0_3_ambiguity_review"]
    assert x["three_way_cluster"] is False
    assert x["status"]=="KEEP_INHERITED_SHADOW_CANDIDATE"
    assert x["research_candidate_pair_unchanged"]==["胜","平"]
    assert x["formal_protection_grant"] is None


def test_draw_close_to_runner_up_even_without_full_three_way_cluster():
    # Home first, away second, draw third but near second: audit, no auto-insert.
    x=inspect(pkt(p=(.51,.235,.255)))["Protection_v0_3_ambiguity_review"]
    assert x["draw_excluded_near_runner_up"] is True
    assert x["research_candidate_pair_unchanged"]==["胜","负"]
    assert x["candidate_release_for_research"] is False


def test_official_minus_one_let_draw_is_home_margin_one():
    x=inspect(jc_pkt(-1,"让负"))["S4_v1_9_margin_score_decision_review"]
    assert x["official_line"]==-1
    assert x["signed_margin_required_for_let_draw"]==1
    assert x["exact_let_draw_probability"]==pytest.approx(.10)
    assert any(v["score"]=="1:0" and v["jc_outcome"]=="让平" for v in x["score_top3_jc_mapping"])
    assert x["frozen_pick_unchanged"]=="让负"


def test_official_plus_one_let_draw_is_away_margin_one():
    x=inspect(jc_pkt(+1,"让胜"))["S4_v1_9_margin_score_decision_review"]
    assert x["signed_margin_required_for_let_draw"]==-1
    assert x["exact_let_draw_probability"]==pytest.approx(.08)
    assert x["frozen_pick_unchanged"]=="让胜"


def test_official_minus_two_and_plus_two_exact_boundary():
    minus=inspect(jc_pkt(-2,"让负"))["S4_v1_9_margin_score_decision_review"]
    plus=inspect(jc_pkt(+2,"让胜"))["S4_v1_9_margin_score_decision_review"]
    assert minus["signed_margin_required_for_let_draw"]==2
    assert minus["exact_let_draw_probability"]==pytest.approx(.30)
    assert plus["signed_margin_required_for_let_draw"]==-2
    assert plus["exact_let_draw_probability"]==pytest.approx(.07)


def test_score_top1_vs_handicap_aggregate_not_mistaken_as_mathematical_inconsistency():
    x=inspect(jc_pkt(-1,"让负"))["S4_v1_9_margin_score_decision_review"]
    assert x["review_required"] is True
    assert x["research_top1_aggregated"]=="让负"
    assert x["top_score_unchanged"]["jc_outcome"]=="让胜"
    assert x["top_score_vs_marginal_disagreement_is_not_a_math_error"] is True
    assert x["frozen_pick_modified"] is False


def test_let_draw_close_to_aggregate_first_triggers_watch_without_direction_switch():
    # Off -2: let draw .30 vs let lose .60; not a close watch in base matrix.
    x=inspect(jc_pkt(-2,"让平"))["S4_v1_9_margin_score_decision_review"]
    assert x["frozen_pick_unchanged"]=="让平"
    assert x["frozen_pick_modified"] is False
    assert x["research_top1_aggregated"]=="让负"


def test_missing_official_line_is_unknown_no_invented_handicap():
    x=inspect(coherent_packet())["S4_v1_9_margin_score_decision_review"]
    assert x["status"].startswith("UNKNOWN")
    assert x["review_required"] is None


def test_asian_handicap_is_rejected_inherited():
    with pytest.raises(ValueError,match="integer"):
        inspect(jc_pkt(-1.5,"让平"))


def test_returned_player_only_called_up_not_assumed_more_effective():
    p=pkt(); p["squad_movements"]=[event("squad_return")]
    x=inspect(p)["ESR_v0_2_squad_return_verification"]
    assert x["callups_or_returns_not_confirmed_to_start"]==1
    assert x["effective_squad_rating_adjustment"] is False
    assert x["new_risk_family_votes"]==0


def test_verified_official_return_is_not_automatic_positive_rating():
    p=pkt(); p["lineup_snapshots"]={"home":{"official":snap("official","n")}}
    p["squad_movements"]=[event("squad_return",player="n0"),event("confirmed_starter",player="n0")]
    x=inspect(p)["ESR_v0_2_squad_return_verification"]
    assert x["verified_official_starter_events"]==1
    assert x["callups_or_returns_not_confirmed_to_start"]==0
    assert all(z["verified_in_official_xi"] for z in x["events"])
    assert x["effective_squad_rating_adjustment"] is False


def test_false_confirmed_starter_rejected_without_official_xi():
    p=pkt(); p["squad_movements"]=[event("confirmed_starter")]
    with pytest.raises(ValueError,match="requires official"):
        inspect(p)


def test_projected_starter_requires_precutoff_projected_xi():
    p=pkt(); p["squad_movements"]=[event("projected_starter")]
    with pytest.raises(ValueError,match="requires projected"):
        inspect(p)


def test_unavailable_in_official_xi_rejected():
    p=pkt(); p["lineup_snapshots"]={"home":{"official":snap("official","n")}}
    p["squad_movements"]=[event("confirmed_unavailable",player="n0")]
    with pytest.raises(ValueError,match="conflicts"):
        inspect(p)


def test_postcutoff_squad_event_rejected():
    p=pkt(); p["squad_movements"]=[event(stamp="2026-11-04T13:00:00+08:00")]
    with pytest.raises(ValueError,match="post-cutoff"):
        inspect(p)


def test_duplicate_squad_event_rejected():
    p=pkt(); p["squad_movements"]=[event(),event()]
    with pytest.raises(ValueError,match="duplicate"):
        inspect(p)


def test_modal_draw_score_can_coexist_with_wdl_win_without_flip():
    p=coherent_packet()
    for row in p["score_matrix"]:
        if row["score"]=="2:2":row["probability"]=.22
        if row["score"]=="1:1":row["probability"]=.05
        if row["score"]=="0:0":row["probability"]=.03
        if row["score"]=="2:0":row["probability"]=.13
        if row["score"]=="3:1":row["probability"]=.17
    # Shift of 0.07 mass from goal2 to goal4; +.07 from 2:0 to 3:1 offsets
    # sum in goal4, while drawn 1:1/0:0 shifts another .07 to 2:2.
    p["goal_distribution"]={k:0.0 for k in ("0","1","2","3","4","5","6","7+")}
    for row in p["score_matrix"]:
        h,a=map(int,row["score"].split(":")); n=h+a
        p["goal_distribution"][str(n) if n<=6 else "7+"]+=row["probability"]
    x=inspect(p)
    gs=x["GS1_6_score_concentration_review"]
    assert gs["score_modal_result"]=="平"
    assert gs["raw_wdl_top1"]=="胜"
    assert gs["score_modal_result_differs_from_wdl_mode"] is True
    assert x["outcome_probabilities_unchanged"]==[.5,.3,.2]


def test_top3_concentration_sum_and_coverage():
    x=inspect(coherent_packet())["GS1_6_score_concentration_review"]
    assert x["score_top3_mass"]==pytest.approx(.45)
    assert x["mass_outside_score_top3"]==pytest.approx(.55)
    assert x["score_top3_unchanged"]==["2:0","2:2","1:0"]


def test_score_matrix_missing_does_not_invent_top3():
    x=inspect(pkt())["GS1_6_score_concentration_review"]
    assert x["status"].startswith("UNKNOWN")
    assert x["score_top3_mass"] is None


def test_inplay_info_rejected_even_when_squad_movement_provided():
    p=pkt(); p["squad_movements"]=[event()]; p["red_card"]="home"
    with pytest.raises(ValueError,match="postmatch or in-play"):
        inspect(p)


def test_recaps_are_conversation_only_not_training():
    from pathlib import Path
    import json
    path=Path(__file__).with_name("RECAP_20261112_6_MATCHES_CONVERSATION_ONLY.json")
    audit=audit_recap(json.loads(path.read_text(encoding="utf-8")))
    assert audit["production_score_eligible"] is False
    assert audit["training_or_calibration_performed"] is False
    assert audit["all_research_directions"]["unique_hit"]=={"hits":5,"n":6}
    assert audit["all_research_directions"]["protection_hit"]=={"hits":5,"n":6}
    assert audit["all_research_directions"]["jc_hit"]=={"hits":2,"n":6}
    assert audit["all_research_directions"]["goals_top3_hit"]=={"hits":6,"n":6}
    assert audit["all_research_directions"]["score_top3_hit"]=={"hits":5,"n":6}
    assert audit["all_research_directions"]["score_top1_hit"]=={"hits":2,"n":6}
    assert audit["ordinary_sale_subset"]["unique_hit"]=={"hits":4,"n":5}
    assert audit["let_draw_actual_count"]==3
