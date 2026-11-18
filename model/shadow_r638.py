"""M79.3.6 Shadow R6.3.8: lineup-shift review, exact JC handicap
margin exposure and 0/1/7+ goal-tail integrity. Research only.

The Production path and all inherited research probabilities, picks and grants
are immutable. Nothing learned from post-match scores enters prematch inspect.
"""
from __future__ import annotations
from typing import Any
import math
import shadow_r637 as r637
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.8_20261112"
PROHIBITED_PREMATCH = {"actual_score", "final_score", "full_time_score",
                        "red_card", "in_play_events", "postmatch_result",
                        "actual_half_time_score"}


def _snapshot(value: Any, side: str, kind: str, cutoff) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"lineup_snapshots.{side}.{kind} must be a source-backed object")
    basis = {"reference": "last_league_xi",
             "projected": "precutoff_projected_xi",
             "official": "official_starting_xi"}[kind]
    if value.get("basis") != basis:
        raise ValueError(f"lineup_snapshots.{side}.{kind}.basis must be {basis}")
    sid, stamp = r637._time_record(value, f"lineup_snapshots.{side}.{kind}", cutoff)
    xi = value.get("player_ids")
    if not isinstance(xi, list) or len(xi) != 11 or any(not isinstance(x,str) or not x.strip() for x in xi) or len(set(xi)) != 11:
        raise ValueError(f"lineup_snapshots.{side}.{kind}.player_ids requires 11 distinct nonblank strings")
    return {"player_ids": set(xi), "source_id": sid, "observed_at": stamp, "basis": basis}


def _lineup_change_audit(packet: dict, parent: dict, direction: str) -> dict:
    """Expected-vs-official surprises and reference-vs-official rotation are
    different diagnostics, and both belong to the single roster family.
    """
    raw = packet.get("lineup_snapshots")
    if raw is None:
        return {"version": "LCRG_v0.1", "status": "UNKNOWN_NO_TIMESTAMPED_LINEUP_SNAPSHOTS",
                "side_audits": {}, "selected_side": "home" if direction == "胜" else "away" if direction == "负" else None,
                "selected_side_review": "UNKNOWN", "extra_core_hold": False,
                "independent_risk_families_added": 0, "probability_adjustment": False}
    if not isinstance(raw, dict) or not set(raw).issubset({"home", "away"}):
        raise ValueError("lineup_snapshots must contain only home/away objects")
    cutoff = base._time(packet["cutoff"], "cutoff")
    audits = {}
    for side in ("home", "away"):
        group = raw.get(side)
        if group is None:
            audits[side] = {"status": "UNKNOWN_SIDE_MISSING", "reference_rotation_count": None,
                            "projected_surprise_count": None, "review": "UNKNOWN"}
            continue
        if not isinstance(group, dict) or not set(group).issubset({"reference", "projected", "official"}):
            raise ValueError(f"lineup_snapshots.{side} must contain only reference/projected/official")
        snapshots = {kind: _snapshot(group.get(kind), side, kind, cutoff)
                     for kind in ("reference", "projected", "official")}
        official = snapshots["official"]
        for kind in ("reference", "projected"):
            older = snapshots[kind]
            if official is not None and older is not None and older["observed_at"] > official["observed_at"]:
                raise ValueError(f"lineup_snapshots.{side}.{kind} cannot postdate official lineup")
        if official is None:
            audits[side] = {"status": "UNKNOWN_NO_OFFICIAL_XI_AT_CUTOFF",
                            "reference_rotation_count": None, "projected_surprise_count": None,
                            "review": "UNKNOWN"}
            continue
        changes = {}
        for kind, output in (("reference", "reference_rotation_count"),
                             ("projected", "projected_surprise_count")):
            other = snapshots[kind]
            changes[output] = len(other["player_ids"] - official["player_ids"]) if other else None
        rotation, surprise = changes["reference_rotation_count"], changes["projected_surprise_count"]
        # Heuristic observation triggers, not fitted bet-selection or probability thresholds.
        if rotation is not None and rotation >= 6:
            review = "HOLD_CORE_LARGE_REFERENCE_ROTATION_NEEDS_ROLE_QUALITY_REVIEW"
        elif surprise is not None and surprise >= 4:
            review = "HOLD_CORE_LARGE_PROJECTED_LINEUP_SURPRISE"
        elif (rotation is not None and rotation >= 3) or (surprise is not None and surprise >= 2):
            review = "WATCH_MATERIAL_LINEUP_CHANGE"
        elif rotation is None and surprise is None:
            review = "UNKNOWN_NO_REFERENCE_OR_PROJECTION"
        else:
            review = "NO_LARGE_LINEUP_CHANGE_DETECTED"
        audits[side] = {"status": "OFFICIAL_XI_COMPARED" if rotation is not None or surprise is not None else "OFFICIAL_XI_ONLY",
                        **changes, "review": review,
                        "official_source_id": official["source_id"],
                        "official_observed_at": official["observed_at"],
                        "comparison_kind": "headcount_only_not_player_quality_or_motivation"}
    selected = "home" if direction == "胜" else "away" if direction == "负" else None
    selected_review = audits[selected]["review"] if selected else "NOT_APPLICABLE_DRAW"
    extra_hold = selected_review.startswith("HOLD_CORE")
    return {"version": "LCRG_v0.1", "status": "REVIEWED" if selected_review not in ("UNKNOWN", "UNKNOWN_NO_REFERENCE_OR_PROJECTION") else "UNKNOWN",
            "side_audits": audits, "selected_side": selected,
            "selected_side_review": selected_review, "extra_core_hold": extra_hold,
            "independent_risk_families_added": 0,
            "counted_as_roster_only": True,
            "source_time_leakage_allowed": False, "probability_adjustment": False}


def _exact_margin_exposure(packet: dict, parent: dict) -> dict:
    audit = parent.get("S4_v1_7_official_handicap_contract", {})
    matrix = packet.get("score_matrix")
    line = audit.get("official_handicap_line")
    if line is None or not matrix or parent.get("GS1_3_joint_score_audit",{}).get("status") != "JOINT_MATRIX_COHERENT":
        return {"version": "S4_v1.8", "status": "UNKNOWN_OFFICIAL_LINE_OR_COHERENT_MATRIX_MISSING",
                "p_exact_margin_let_draw": None, "margin_score_candidates": [],
                "probability_adjustment": False, "formal_handicap_grant": None}
    target = -line
    matching=[]; mass=0.0
    for row in matrix:
        h,a=map(int,row["score"].split(":"))
        if h-a == target:
            mass += float(row["probability"])
            matching.append({"score": row["score"], "probability": float(row["probability"])})
    matches = sorted(matching, key=lambda x: (-x["probability"], x["score"]))
    hp = audit.get("handicap_probabilities", {})
    if abs(mass - hp.get("让平", float("nan"))) > .002:
        raise ValueError("S4 exact-margin mass inconsistent with JC let-draw probability")
    ranked = sorted(("让胜", "让平", "让负"), key=lambda x: (-hp[x], ("让胜", "让平", "让负").index(x)))
    score_top3 = parent.get("GS1_5_score_family_runner_up_audit", {}).get("score_top3") or []
    return {"version":"S4_v1.8", "status":"EXACT_JC_MARGIN_AUDITED",
            "official_line":line, "required_home_minus_away_margin":target,
            "p_exact_margin_let_draw":round(mass,6),
            "let_draw_rank":ranked.index("让平")+1,
            "gap_to_top_handicap_probability":round(hp[ranked[0]]-hp["让平"],6),
            "margin_score_candidates":matches[:3],
            "top3_contains_exact_margin_score":bool(set(x["score"] for x in matches)&set(score_top3)),
            "one_goal_let_draw_case":abs(line)==1,
            "watch_exact_one_goal_let_draw":abs(line)==1 and ranked.index("让平")<=1,
            "research_pick_unchanged":audit.get("research_top1"),
            "frozen_pick_unchanged":audit.get("frozen_handicap_pick"),
            "probability_adjustment":False, "formal_handicap_grant":None}


def _tail_integrity_audit(packet: dict, parent: dict) -> dict:
    buckets = packet.get("goal_distribution")
    if buckets is None:
        return {"version":"RC2.6", "status":"UNKNOWN_NO_GOAL_BUCKET_DISTRIBUTION",
                "exact_goal_top3_recomputed":None, "probability_adjustment":False}
    keys = tuple(str(n) for n in range(7)) + ("7+",)
    if not isinstance(buckets,dict) or set(buckets) != set(keys) or any(type(v) not in (float,int) or not math.isfinite(v) or v<0 for v in buckets.values()) or abs(sum(buckets.values())-1)>.002:
        raise ValueError("goal_distribution must be a valid normalized 0..6,7+ probability dictionary")
    valid_exact = sorted((k for k in keys if k!="7+"), key=lambda k:(-buckets[k], int(k)))
    r25 = parent.get("RC2_5_exact_bucket_router",{})
    return {"version":"RC2.6", "status":"LOW_HIGH_TAIL_MASS_AUDITED",
            "p_0":round(buckets["0"],6),"p_1":round(buckets["1"],6),
            "p_7plus_aggregate":round(buckets["7+"],6),
            "p_central_2_3":round(buckets["2"]+buckets["3"],6),
            "p_low_0_1":round(buckets["0"]+buckets["1"],6),
            "exact_0_to_6_rank_watch":valid_exact[:3],
            "seven_plus_is_aggregate_not_exact_integer":True,
            "exact_seven_plus_score_candidate_not_assumed":True,
            "tail_router_status_unchanged":r25.get("status"),
            "no_new_tail_slots":True,
            "probability_adjustment":False}


def inspect(packet: dict) -> dict:
    if not isinstance(packet,dict):
        raise ValueError("prematch packet must be object")
    if PROHIBITED_PREMATCH & set(packet):
        raise ValueError("postmatch or in-play fields forbidden in prematch packet")
    parent = r637.inspect(packet)
    direction = parent["Selection_Efficiency_v0_5"]["raw_direction"]
    lineup = _lineup_change_audit(packet,parent,direction)
    margin = _exact_margin_exposure(packet,parent)
    tail = _tail_integrity_audit(packet,parent)
    selection = dict(parent["Selection_Efficiency_v0_5"])
    selection["version"] = "Selection_Efficiency_v0.6"
    selection["inherited_core_review"] = selection["core_candidate_review"]
    selection["lineup_change_review"] = lineup["selected_side_review"]
    if lineup["extra_core_hold"] and selection["core_candidate_review"] == "RESEARCH_CORE_REVIEW_READY_NOT_GRANTED":
        selection["core_candidate_review"] = "HOLD_CORE_LARGE_LINEUP_CHANGE_MANUAL_ESR_REVIEW"
    selection["core_not_auto_granted"] = True
    flags = list(parent.get("audit_flags_r637",[]))
    if lineup["extra_core_hold"]:
        flags.append("LCRG_LARGE_LINEUP_CHANGE_HOLD_CORE_CANDIDATE")
    elif lineup["selected_side_review"] == "WATCH_MATERIAL_LINEUP_CHANGE":
        flags.append("LCRG_MATERIAL_LINEUP_CHANGE_WATCH")
    if margin.get("watch_exact_one_goal_let_draw"):
        flags.append("S4_ONE_GOAL_LET_DRAW_WITHIN_TOP2_WATCH")
    if tail.get("status") == "LOW_HIGH_TAIL_MASS_AUDITED":
        flags.append("RC26_TAIL_MASS_OBSERVED_NO_AUTOMATIC_ROUTING_CHANGE")
    return {**parent, "version":VERSION,
            "LCRG_v0_1_lineup_rotation_review":lineup,
            "S4_v1_8_exact_margin_exposure":margin,
            "RC2_6_low_high_tail_integrity":tail,
            "Selection_Efficiency_v0_6":selection,
            "audit_flags_r638":flags,
            "outcome_probabilities_unchanged":parent["outcome_probabilities_unchanged"],
            "probability_adjustment_applied":False,
            "automatic_direction_flip":False,
            "formal_single_grant":None,"formal_core_grant":None,
            "formal_protection_grant":None,"formal_handicap_grant":None,
            "production_changed":False,
            "notes_r638":[
                "11 Nov six-match recap is development diagnosis only: no frozen 6-match predictions or independent validation claimed.",
                "Strong-favorite starting-XI rotation and projected-vs-official surprise are different, timestamp-guarded roster diagnostics.",
                "Starting-XI change counts are not player-quality ratings; they cannot flip WDL or count as a new independent family.",
                "JC let-draw probability is exactly the signed margin family, derived from the existing joint-score matrix.",
                "7+ aggregate total-goals bucket is not a specific integer and must not be misrepresented as one.",
                "In-play cards, goals and final results are segregated from prematch inspect.",
                "No parameters or weights were fitted to the six observed matches.",
            ]}
