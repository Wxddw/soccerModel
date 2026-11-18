"""M79.3.6 Shadow R6.3.9: JC margin/score review, WDL protection
ambiguity, squad-return evidence and score concentration.

Research-only overlay. No new fitted parameters or change of any inherited
probabilities, exact-score rankings, decisions or formal grants.
"""
from __future__ import annotations

from collections import Counter
import math
import re
from typing import Any

import shadow_r638 as r638
import shadow_r636 as r636
import shadow_r637 as r637
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.9_20261113"
WDL = ("胜", "平", "负")
JC = ("让胜", "让平", "让负")
SQUAD_EVENT_KINDS = {"squad_return", "new_callup", "projected_starter",
                     "confirmed_starter", "confirmed_unavailable"}
# Unfitted shadow-only ambiguity checks. NOT new bet-selection thresholds.
THREE_WAY_CLUSTER_RANGE = .05
DRAW_RUNNER_UP_GAP_WATCH = .03
JC_LET_DRAW_TOP_GAP_WATCH = .05
_SCORE_PATTERN = re.compile(r"^(0|[1-9][0-9]*):(0|[1-9][0-9]*)$")


def _score(score: str) -> tuple[int, int]:
    if not isinstance(score, str) or _SCORE_PATTERN.fullmatch(score) is None:
        raise ValueError("score must be canonical nonnegative integer home:away")
    h, a = map(int, score.split(":"))
    return h, a


def _research_protection(packet: dict, parent: dict) -> dict:
    """Shadow protection ambiguity gate. It does not replace Protection v0.2.

    A 3-way cluster makes the runner-up ordering fragile, not a reason to
    assume a draw or flip the raw Top1.
    """
    p = parent["outcome_probabilities_unchanged"]
    idx = r636._rank_wdl(p)
    labels = [WDL[i] for i in idx]
    inherited = parent["Protection_v0_2"]
    top, second, third = (p[i] for i in idx)
    cluster = top-third <= THREE_WAY_CLUSTER_RANGE + 1e-12
    candidate = list(inherited["research_candidate_pair"])
    draw_excluded = "平" not in candidate
    near_runner = draw_excluded and (second - p[1] <= DRAW_RUNNER_UP_GAP_WATCH + 1e-12)
    flags = []
    if top < .40:
        flags.append("OUTCOME_TOP1_UNDER_40_PERCENT_RESEARCH_DIRECTION_ONLY")
    if cluster:
        flags.append("THREE_WAY_CLUSTER_MANUAL_REVIEW_NO_PROTECTION_RELEASE")
    if near_runner:
        flags.append("EXCLUDED_DRAW_WITHIN_3PP_OF_RUNNER_UP")
    if inherited["status"].startswith("MANUAL_REVIEW"):
        flags.append("INHERITED_PROTECTION_MANUAL_REVIEW")
    review = cluster or near_runner or bool(inherited["status"].startswith("MANUAL_REVIEW"))
    # A proposed pair is only a research candidate, NEVER a bet/grant.
    return {
        "version": "Protection_v0.3",
        "status": "MANUAL_REVIEW_PROTECTION_AMBIGUITY" if review else "KEEP_INHERITED_SHADOW_CANDIDATE",
        "raw_direction_unchanged": labels[0],
        "wdl_probabilities_unchanged": list(p),
        "research_candidate_pair_unchanged": candidate,
        "protected_draw_not_auto_inserted": True,
        "candidate_release_for_research": bool(inherited["research_proposed_protection"] is not None and not review),
        "manual_review_candidate_pair": candidate if review else None,
        "top1_minus_third_gap": round(top-third, 6),
        "draw_minus_runner_up_gap": round(p[1]-second, 6),
        "three_way_cluster": cluster,
        "draw_excluded_near_runner_up": near_runner,
        "thresholds": {"three_way_range_pp": 5.0, "excluded_draw_to_runner_pp": 3.0},
        "flags": flags,
        "formal_protection_grant": None,
        "automatic_pair_replacement": False,
        "probability_adjustment": False,
    }


def _jc_margin_score_review(packet: dict, parent: dict) -> dict:
    """Compare the *frozen* JC pick to integrated margin and exact-score modes.

    A single score mode != aggregate margin mode is not a mathematical error.
    It triggers a review if there is score/decision tension, but never forces
    let-draw or replaces the frozen pick.
    """
    inherited = parent.get("S4_v1_7_official_handicap_contract", {})
    checked = parent.get("S4_v1_8_exact_margin_exposure", {})
    gs = parent.get("GS1_3_joint_score_audit", {})
    matrix = packet.get("score_matrix")
    if (checked.get("status") != "EXACT_JC_MARGIN_AUDITED" or
        gs.get("status") != "JOINT_MATRIX_COHERENT" or not matrix):
        return {"version": "S4_v1.9", "status": "UNKNOWN_OFFICIAL_JC_OR_JOINT_MATRIX_MISSING",
                "review_required": None, "score_mode": None, "official_line": None,
                "formal_handicap_grant": None, "probability_adjustment": False}
    line = inherited["official_handicap_line"]
    hp = inherited["handicap_probabilities"]
    ordered = sorted(matrix, key=lambda r: (-float(r["probability"]), r["score"]))
    top3 = ordered[:3]
    outcomes = []
    for row in top3:
        h, a = _score(row["score"])
        adjusted = h + line - a
        label = "让胜" if adjusted > 0 else "让平" if adjusted == 0 else "让负"
        outcomes.append({"score": row["score"], "probability": round(float(row["probability"]), 6),
                         "jc_outcome": label, "net_margin": h-a})
    rank = sorted(JC, key=lambda x: (-hp[x], JC.index(x)))
    highest, runner = rank[:2]
    frozen = inherited["frozen_handicap_pick"]
    let_draw_gap = hp[highest] - hp["让平"]
    top_score_label = outcomes[0]["jc_outcome"]
    among_top3 = sum(x["jc_outcome"] == "让平" for x in outcomes)
    flags = []
    if top_score_label != highest:
        flags.append("SCORE_MODE_DIFFERS_FROM_AGGREGATED_JC_MODE_NOT_MATH_ERROR")
    if frozen != highest:
        flags.append("FROZEN_JC_PICK_DIFFERS_FROM_AGGREGATED_JC_MODE")
    if frozen != top_score_label:
        flags.append("FROZEN_JC_PICK_DIFFERS_FROM_SCORE_TOP1_MAPPED_JC")
    if (let_draw_gap <= JC_LET_DRAW_TOP_GAP_WATCH + 1e-12 and highest != "让平"):
        flags.append("LET_DRAW_WITHIN_5PP_OF_JC_TOP1_MANUAL_REVIEW")
    if among_top3 >= 2 and frozen != "让平":
        flags.append("MULTIPLE_SCORE_TOP3_IMPLY_LET_DRAW_WATCH")
    if checked.get("p_exact_margin_let_draw") is None:
        raise ValueError("Missing exact margin probability despite coherent matrix")
    if not math.isclose(float(hp["让平"]), float(checked["p_exact_margin_let_draw"]), abs_tol=.002):
        raise ValueError("JC let-draw marginal conflicts with S4 exact-margin audit")
    return {"version": "S4_v1.9", "status": "JC_SCORE_MARGIN_CONSISTENT_REVIEW" if flags else "JC_SCORE_MARGIN_CLEAR",
            "official_line": line, "signed_margin_required_for_let_draw": -line,
            "handicap_probabilities_unchanged": dict(hp),
            "research_top1_aggregated": highest,
            "research_runner_up_aggregated": runner,
            "frozen_pick_unchanged": frozen,
            "exact_let_draw_probability": checked["p_exact_margin_let_draw"],
            "let_draw_gap_to_top": round(let_draw_gap, 6),
            "top_score_unchanged": outcomes[0],
            "score_top3_jc_mapping": outcomes,
            "top3_let_draw_score_count": among_top3,
            "review_required": bool(flags), "review_reasons": flags,
            "threshold_pp_unfitted_shadow_only": 5.0,
            "top_score_vs_marginal_disagreement_is_not_a_math_error": True,
            "formal_handicap_grant": None,
            "frozen_pick_modified": False,
            "probability_adjustment": False}


def _squad_return_quality_gate(packet: dict, parent: dict) -> dict:
    """Track squad returns and callups without pretending to know added strength.

    The official XI must be a timestamp-verified snapshot before a
    `confirmed_starter` label is accepted. All movements count as roster ONLY.
    """
    events = packet.get("squad_movements")
    if events is None:
        return {"version": "ESR_v0.2", "status": "UNKNOWN_NO_SQUAD_MOVEMENT_SOURCES",
                "events": [], "source_event_count": 0, "new_risk_family_votes": 0,
                "effective_squad_rating_adjustment": False, "probability_adjustment": False}
    if not isinstance(events, list):
        raise ValueError("squad_movements must be a list")
    snapshots = packet.get("lineup_snapshots") or {}
    cutoff = base._time(packet["cutoff"], "cutoff")
    seen=set(); rows=[]; verified_starts=0; returns_only=0
    for idx,rec in enumerate(events):
        if not isinstance(rec, dict):
            raise ValueError("squad_movements event must be a source-backed object")
        kind, side, player=rec.get("kind"), rec.get("side"), rec.get("player_id")
        if kind not in SQUAD_EVENT_KINDS or side not in ("home","away"):
            raise ValueError("squad_movements kind or side invalid")
        if not isinstance(player,str) or not player.strip():
            raise ValueError("squad_movements.player_id required")
        unique=(side,player,kind)
        if unique in seen: raise ValueError("duplicate squad movement event")
        seen.add(unique)
        sid, stamp=r637._time_record(rec, f"squad_movements[{idx}]",cutoff)
        group=snapshots.get(side) or {}
        official=r638._snapshot(group.get("official"), side, "official", cutoff)
        projected=r638._snapshot(group.get("projected"), side, "projected", cutoff)
        in_official=official is not None and player in official["player_ids"]
        in_projected=projected is not None and player in projected["player_ids"]
        if kind=="confirmed_starter" and not in_official:
            raise ValueError("confirmed_starter requires official precutoff XI with matching player")
        if kind=="confirmed_unavailable" and in_official:
            raise ValueError("confirmed_unavailable conflicts with official precutoff XI")
        if kind=="projected_starter" and not in_projected:
            raise ValueError("projected_starter requires projected precutoff XI")
        if kind=="confirmed_starter": verified_starts+=1
        if kind in ("squad_return", "new_callup") and not in_official: returns_only+=1
        rows.append({"side":side,"player_id":player,"kind":kind,"source_id":sid,
                     "observed_at":stamp,"verified_in_official_xi":in_official,
                     "verified_in_projected_xi":in_projected,
                     "effect_on_team_rating":"UNKNOWN_NEEDS_ESR_RATING_AND_EXPECTED_MINUTES",
                     "independent_evidence_family":"roster"})
    return {"version":"ESR_v0.2", "status":"MOVEMENTS_AUDITED_NO_AUTO_STRENGTH_INFERENCE" if rows else "NO_MOVEMENTS_REPORTED",
            "events":rows,"source_event_count":len(rows),"verified_official_starter_events":verified_starts,
            "callups_or_returns_not_confirmed_to_start":returns_only,
            "roster_family_only":True,"new_risk_family_votes":0,
            "effective_squad_rating_adjustment":False,"probability_adjustment":False}


def _score_concentration_review(packet: dict, parent: dict) -> dict:
    matrix=packet.get("score_matrix")
    if not matrix or parent.get("GS1_3_joint_score_audit", {}).get("status")!="JOINT_MATRIX_COHERENT":
        return {"version":"GS1.6", "status":"UNKNOWN_NO_COHERENT_MATRIX",
                "score_top3_mass":None,"probability_adjustment":False}
    rows=sorted(matrix,key=lambda r:(-float(r["probability"]),r["score"]))
    top3=rows[:3]
    mass=sum(float(x["probability"]) for x in top3)
    by_result=Counter()
    by_goal=Counter()
    for x in top3:
        h,a=_score(x["score"]); p=float(x["probability"])
        by_result["胜" if h>a else "负" if h<a else "平"]+=1
        by_goal[str(h+a) if h+a<=6 else "7+"]+=1
    raw=parent["Selection_Efficiency_v0_6"]["raw_direction"]
    # Modal score may be draw despite aggregate raw home-win; not an error.
    top_h,top_a=_score(top3[0]["score"])
    modal_result="胜" if top_h>top_a else "负" if top_h<top_a else "平"
    return {"version":"GS1.6", "status":"JOINT_MATRIX_CONCENTRATION_REVIEWED",
            "score_top3_unchanged":[x["score"] for x in top3],
            "score_top1_probability":round(float(top3[0]["probability"]),6),
            "score_top3_mass":round(mass,6),
            "mass_outside_score_top3":round(1-mass,6),
            "top3_outcome_counts":{k:by_result.get(k,0) for k in WDL},
            "top3_goal_bucket_counts":dict(by_goal),
            "raw_wdl_top1":raw,"score_modal_result":modal_result,
            "score_modal_result_differs_from_wdl_mode":modal_result!=raw,
            "modal_result_disagreement_is_not_mathematical_inconsistency":True,
            "no_reranking_or_goal_slot_override":True,
            "probability_adjustment":False}


def inspect(packet: dict) -> dict:
    # R6.3.8 already denies postmatch/in-play fields at the input boundary.
    parent=r638.inspect(packet)
    protection=_research_protection(packet,parent)
    margin=_jc_margin_score_review(packet,parent)
    squad=_squad_return_quality_gate(packet,parent)
    gs=_score_concentration_review(packet,parent)
    selection=dict(parent["Selection_Efficiency_v0_6"])
    selection["version"]="Selection_Efficiency_v0.7"
    selection["protection_ambiguity_review"]=protection["status"]
    selection["direction_unchanged_due_to_protection_audit"]=True
    flags=list(parent.get("audit_flags_r638",[]))
    flags.extend(protection.get("flags",[]))
    flags.extend(margin.get("review_reasons",[]))
    if squad.get("callups_or_returns_not_confirmed_to_start",0):
        flags.append("SQUAD_RETURN_CALLUP_NOT_EQUAL_CONFIRMED_START_OR_RATING_GAIN")
    if gs.get("score_modal_result_differs_from_wdl_mode"):
        flags.append("SCORE_MODE_VS_WDL_MODE_DIFFERENCE_WATCH_NOT_MATH_ERROR")
    return {**parent,"version":VERSION,
            "Protection_v0_3_ambiguity_review":protection,
            "S4_v1_9_margin_score_decision_review":margin,
            "ESR_v0_2_squad_return_verification":squad,
            "GS1_6_score_concentration_review":gs,
            "Selection_Efficiency_v0_7":selection,
            "audit_flags_r639":list(dict.fromkeys(flags)),
            "outcome_probabilities_unchanged":parent["outcome_probabilities_unchanged"],
            "probability_adjustment_applied":False,"automatic_direction_flip":False,
            "formal_single_grant":None,"formal_core_grant":None,
            "formal_protection_grant":None,"formal_handicap_grant":None,
            "production_changed":False,
            "notes_r639":[
              "12 Nov 6-match conversation recap is descriptive development only, not official prematch data or independent validation.",
              "No static let-draw probability boosts or posthoc net-margin changes.",
              "Top1 scoreline can map to a different JC category than the integrated margin mode without a mathematical error.",
              "All R6.3.8 and earlier modules are left intact; any manual-review flag cannot grant a formal pick.",
              "No result, halftime result or red-card event passed into prematch inspect()."]}
