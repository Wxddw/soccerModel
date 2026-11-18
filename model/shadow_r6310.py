"""M79.3.6 Production frozen; Shadow R6.3.10 read-only review overlay.

Diagnostic extension after November 13, 2026 conversation recap. Neither final
scores nor any replay samples can be supplied to prematch inspect. All joint
probabilities, direction choices, Top3 slots and formal grants are inherited.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any
import math

import shadow_r639 as prev
import shadow_r637 as r637
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.10_20261114"
WDL = ("胜", "平", "负")
JC = ("让胜", "让平", "让负")
GOAL_BUCKETS = tuple(map(str, range(7))) + ("7+",)
# Recap-only values are forbidden even if a legacy implementation does not know the key.
REPLAY_ONLY_FIELDS = {"actual_halftime", "actual_wdl", "actual_jc", "actual_goal",
                      "actual_htft", "final_result", "match_result", "recap",
                      "actual_result", "actual_fulltime", "actual_half_time",
                      "actual_goal_count", "postmatch_outcome",
                      "actual_score", "postmatch_score", "actual_half_time_score",
                      "red_card", "in_play_events"}


def _valid_joint(packet: dict, parent: dict) -> list | None:
    matrix = packet.get("score_matrix")
    if not matrix or parent.get("GS1_3_joint_score_audit", {}).get("status") != "JOINT_MATRIX_COHERENT":
        return None
    return matrix


def _margin_boundary_v20(packet: dict, parent: dict) -> dict:
    matrix = _valid_joint(packet, parent)
    prev_jc = parent.get("S4_v1_9_margin_score_decision_review", {})
    contract = parent.get("S4_v1_7_official_handicap_contract", {})
    if matrix is None or prev_jc.get("status", "").startswith("UNKNOWN") or contract.get("official_handicap_line") is None:
        return {"version": "S4_v2.0", "status": "UNKNOWN_NO_OFFICIAL_JC_AND_COHERENT_JOINT",
                "signed_margin_probabilities": None, "formal_handicap_grant": None,
                "probability_adjustment": False}
    line = contract["official_handicap_line"]
    frozen_pick = contract["frozen_handicap_pick"]
    marginal = {key: 0.0 for key in JC}
    by_margin = defaultdict(float)
    margin_rows = defaultdict(list)
    for row in matrix:
        home, away = prev._score(row["score"])
        d = home - away
        p = float(row["probability"])
        by_margin[d] += p
        margin_rows[d].append((row["score"], p))
        marginal["让胜" if d + line > 0 else "让平" if d + line == 0 else "让负"] += p
    old = contract["handicap_probabilities"]
    if any(abs(marginal[k] - float(old[k])) > .002 for k in JC):
        raise ValueError("R6.3.10 JC marginal inconsistent with inherited contract")
    if abs(sum(marginal.values()) - 1) > .002:
        raise ValueError("R6.3.10 JC outcomes must be collectively exhaustive")
    target = -line
    rank = sorted(JC, key=lambda x: (-marginal[x], JC.index(x)))
    first, second = rank[:2]
    gap = marginal[first] - marginal[second]
    draw_gap = marginal[first] - marginal["让平"]
    flags = []
    if gap <= .05 + 1e-12:
        flags.append("JC_TOP_TWO_WITHIN_5PP_MANUAL_REVIEW")
    if first != "让平" and draw_gap <= .05 + 1e-12:
        flags.append("LET_DRAW_WITHIN_5PP_OF_JC_TOP1")
    if first != frozen_pick:
        flags.append("FROZEN_JC_CHOICE_DIFFERS_FROM_FULL_MARGIN_MARGINAL")
    # A score-mode / JC marginal conflict alone is not a mathematical failure.
    if prev_jc.get("review_required"):
        flags.append("INHERITED_SCORE_JC_DECISION_TENSION_WATCH")
    top_margins = sorted(by_margin, key=lambda d: (-by_margin[d], d))
    # Show the signed home-minus-away margin, including negative away wins.
    distribution = {str(d): round(by_margin[d], 9) for d in sorted(by_margin)}
    boundary = {}
    for d in (target-1, target, target+1):
        boundary[str(d)] = {
            "probability": round(by_margin.get(d, 0.0), 9),
            "top_score_examples": [
                {"score": s, "probability": round(p, 9)}
                for s, p in sorted(margin_rows.get(d, []), key=lambda x: (-x[1], x[0]))[:3]
            ],
        }
    return {
        "version": "S4_v2.0", "status": "MARGIN_BOUNDARY_REVIEW" if flags else "MARGIN_BOUNDARY_CLEAR",
        "official_jc_integer_line": line,
        "signed_let_draw_margin": target,
        "signed_margin_probabilities": distribution,
        "top_signed_margins": [{"margin": d, "probability": round(by_margin[d], 9)} for d in top_margins[:5]],
        "exact_let_draw_probability": round(by_margin.get(target, 0.0), 9),
        "neighbor_margin_probabilities": boundary,
        "reconstructed_jc_probabilities": {k: round(marginal[k], 9) for k in JC},
        "integrated_jc_first": first,
        "integrated_jc_second": second,
        "jc_top_two_gap": round(gap, 9),
        "frozen_pick_unchanged": frozen_pick,
        "review_required": bool(flags), "review_reasons": flags,
        "finite_score_grid_only_not_unbounded_tail_proof": True,
        "auto_let_draw_boost": False, "auto_pick_switch": False,
        "formal_handicap_grant": None, "probability_adjustment": False,
    }


def _goal_tail_review_v27(packet: dict, parent: dict) -> dict:
    dist = packet.get("goal_distribution")
    if dist is None:
        return {"version": "RC2.7", "status": "UNKNOWN_NO_FROZEN_GOAL_DISTRIBUTION",
                "tail_family_probabilities": None, "probability_adjustment": False}
    # Inherited RC2.6 has already validated keys, normalization and finiteness.
    if set(dist) != set(GOAL_BUCKETS):
        raise ValueError("expected exact 0..6 and separate 7+ aggregate buckets")
    m = {str(k): float(dist[str(k)]) for k in GOAL_BUCKETS}
    if any(not math.isfinite(v) or v < 0 for v in m.values()) or abs(sum(m.values())-1) > .002:
        raise ValueError("invalid frozen goal distribution")
    ranks = sorted((str(x) for x in range(7)), key=lambda k: (-m[k], int(k)))
    tails = {
        "zero": m["0"], "one": m["1"], "four": m["4"],
        "five": m["5"], "six": m["6"], "seven_plus_aggregate": m["7+"],
        "low_0_1": m["0"] + m["1"], "central_2_3": m["2"] + m["3"],
        "high_5_plus": m["5"] + m["6"] + m["7+"],
        "four_plus": m["4"] + m["5"] + m["6"] + m["7+"],
    }
    matrix = _valid_joint(packet, parent)
    matrix_7plus = None
    if matrix is not None:
        matrix_7plus = sum(float(r["probability"]) for r in matrix
                           if sum(prev._score(r["score"])) >= 7)
        if abs(matrix_7plus - m["7+"]) > .015:
            raise ValueError("7+ joint-score mass conflicts with goal_distribution")
    router = parent.get("RC2_5_exact_bucket_router", {})
    return {
        "version": "RC2.7", "status": "TAIL_FAMILY_READ_ONLY_AUDITED",
        "tail_family_probabilities": {k: round(v, 9) for k,v in tails.items()},
        "raw_exact_0_to_6_rank_watch_not_model_final_top3": [int(k) for k in ranks[:3]],
        "seven_plus_is_aggregate_not_exact_goal": True,
        "seven_plus_joint_score_grid_mass": None if matrix_7plus is None else round(matrix_7plus, 9),
        "inherited_precutoff_tail_router_status": router.get("status", "UNKNOWN"),
        "new_tail_votes": 0, "goal_top3_reordered": False,
        "thresholds_refitted": False, "probability_adjustment": False,
    }


def _score_family_review_v17(packet: dict, parent: dict) -> dict:
    matrix = _valid_joint(packet, parent)
    if matrix is None:
        return {"version": "GS1.7", "status": "UNKNOWN_NO_COHERENT_SCORE_MATRIX",
                "score_top3_family_coverage": None, "probability_adjustment": False}
    rows = sorted(matrix, key=lambda r: (-float(r["probability"]), r["score"]))
    top3 = rows[:3]
    by_wdl = defaultdict(float)
    covered_wdl = defaultdict(float)
    both_score = 0.0
    home_zero = 0.0
    away_zero = 0.0
    score_zero_zero = 0.0
    by_exact_goals = defaultdict(float)
    for i, r in enumerate(rows):
        h, a = prev._score(r["score"])
        p = float(r["probability"])
        outcome = "胜" if h > a else "平" if h == a else "负"
        by_wdl[outcome] += p
        if i < 3:
            covered_wdl[outcome] += p
        if h > 0 and a > 0:
            both_score += p
        if h == 0:
            home_zero += p
        if a == 0:
            away_zero += p
        if h == 0 and a == 0:
            score_zero_zero += p
        by_exact_goals[h + a] += p
    coverage = {}
    for k in WDL:
        coverage[k] = {
            "family_mass": round(by_wdl[k],9),
            "covered_by_global_score_top3_mass": round(covered_wdl[k],9),
            "conditional_family_top3_coverage": (round(covered_wdl[k] / by_wdl[k],9)
                if by_wdl[k] > 0 else None),
            "uncovered_family_mass": round(max(0.0, by_wdl[k] - covered_wdl[k]),9),
        }
    max_score_goals = max(by_exact_goals) if by_exact_goals else 0
    return {
        "version": "GS1.7", "status": "JOINT_SCORE_FAMILIES_COVERAGE_AUDITED",
        "score_top3_unchanged": [r["score"] for r in top3],
        "global_score_top3_mass": round(sum(float(r["probability"]) for r in top3), 9),
        "score_top3_family_coverage": coverage,
        "both_teams_score_probability": round(both_score,9),
        "nil_nil_probability": round(score_zero_zero,9),
        "home_zero_goal_probability": round(home_zero,9),
        "away_zero_goal_probability": round(away_zero,9),
        "exact_five_goal_probability_on_matrix": round(by_exact_goals[5],9),
        "seven_plus_aggregate_on_matrix": round(sum(p for n,p in by_exact_goals.items() if n>=7),9),
        "max_total_goals_in_finite_matrix": max_score_goals,
        "top3_not_equal_family_conditional_top2": True,
        "score_top3_reranked": False, "new_score_slots": 0,
        "probability_adjustment": False,
    }


def _objective_context_review_v08(packet: dict, parent: dict) -> dict:
    context = packet.get("competition_context")
    if context is None:
        return {"version": "Selection_Context_v0.8", "status": "UNKNOWN_NO_TIMESTAMPED_CONTEXT",
                "core_manual_review": False, "risk_family_votes_added": 0,
                "probability_adjustment": False}
    if not isinstance(context, dict):
        raise ValueError("competition_context must be source-backed object")
    cutoff = base._time(packet["cutoff"], "cutoff")
    sid, timestamp = r637._time_record(context, "competition_context", cutoff)
    allowed = {"source_id","observed_at","competition_kind","selected_side_objective","allowed_substitutions"}
    if set(context) - allowed:
        raise ValueError("unknown competition_context fields")
    kind = context.get("competition_kind")
    objective = context.get("selected_side_objective", "unknown")
    allowed_subs = context.get("allowed_substitutions")
    if kind not in ("competitive","friendly"):
        raise ValueError("competition_kind must be competitive or friendly")
    if objective not in ("unknown","win_required","draw_sufficient","no_objective_identified"):
        raise ValueError("invalid selected_side_objective")
    if allowed_subs is not None and (type(allowed_subs) is not int or not 0 <= allowed_subs <= 20):
        raise ValueError("allowed_substitutions must be integer 0..20 or absent")
    flags = []
    if objective == "draw_sufficient":
        flags.append("SELECTED_TEAM_DRAW_SUFFICIENT_FOR_OBJECTIVE_CONTEXT_WATCH")
    if kind == "friendly":
        flags.append("FRIENDLY_MATCH_ROTATION_UNCERTAINTY_WATCH")
        if allowed_subs is not None and allowed_subs > 5:
            flags.append("FRIENDLY_EXTENDED_SUBSTITUTION_ALLOWANCE_WATCH")
    if objective == "unknown":
        flags.append("TEAM_OBJECTIVE_UNKNOWN_NOT_A_SAFE_CLEARANCE")
    return {
        "version": "Selection_Context_v0.8",
        "status": "CONTEXT_MANUAL_REVIEW" if any(x != "TEAM_OBJECTIVE_UNKNOWN_NOT_A_SAFE_CLEARANCE" for x in flags) else "CONTEXT_UNKNOWN",
        "source_id": sid, "observed_at": timestamp,
        "competition_kind": kind, "selected_side_objective": objective,
        "allowed_substitutions": allowed_subs,
        "core_manual_review": bool(any(x != "TEAM_OBJECTIVE_UNKNOWN_NOT_A_SAFE_CLEARANCE" for x in flags)),
        "flags": flags,
        "risk_family_votes_added": 0,
        "risk_not_auto_reinterpreted_as_draw_probability": True,
        "automatic_direction_flip": False, "probability_adjustment": False,
    }


def inspect(packet: dict) -> dict:
    # Reject any replay-only values before passing to inherited prematch pipeline.
    if not isinstance(packet, dict):
        raise ValueError("prematch packet must be an object")
    if REPLAY_ONLY_FIELDS.intersection(packet):
        raise ValueError("prematch packet contains postmatch/replay-only fields")
    # Old R6.3.8 separately rejects its own in-play/postmatch keys.
    inherited = prev.inspect(packet)
    margin = _margin_boundary_v20(packet, inherited)
    tails = _goal_tail_review_v27(packet, inherited)
    scores = _score_family_review_v17(packet, inherited)
    context = _objective_context_review_v08(packet, inherited)
    selection = dict(inherited["Selection_Efficiency_v0_7"])
    selection["version"] = "Selection_Efficiency_v0.8"
    selection["objective_context_review"] = context["status"]
    selection["inherited_core_review_unchanged"] = selection.get("core_candidate_review")
    if context["core_manual_review"] and selection.get("core_candidate_review") == "RESEARCH_CORE_REVIEW_READY_NOT_GRANTED":
        selection["core_candidate_review"] = "HOLD_CORE_CONTEXT_MANUAL_REVIEW_NOT_GRANTED"
    selection["probability_adjustment"] = False
    flags = list(inherited.get("audit_flags_r639", []))
    flags.extend(margin.get("review_reasons", []))
    flags.extend(context.get("flags", []))
    return {
        **inherited,
        "version": VERSION,
        "S4_v2_0_signed_margin_boundary_audit": margin,
        "RC2_7_zero_one_four_five_seven_tail_audit": tails,
        "GS1_7_score_family_coverage_audit": scores,
        "Selection_Context_v0_8": context,
        "Selection_Efficiency_v0_8": selection,
        "audit_flags_r6310": list(dict.fromkeys(flags)),
        "outcome_probabilities_unchanged": inherited["outcome_probabilities_unchanged"],
        "probability_adjustment_applied": False,
        "automatic_direction_flip": False,
        "formal_single_grant": None,
        "formal_core_grant": None,
        "formal_protection_grant": None,
        "formal_handicap_grant": None,
        "production_changed": False,
        "postmatch_training_performed": False,
        "notes_r6310": [
            "Nov13 eleven-match conversation recap is diagnostic only, never an independent holdout or training set.",
            "S4 exact JC margin, GS conditional score family and RC tails are all derived from the unchanged pre-match joint distribution.",
            "0 and 7+ can be audit candidates; seven-plus is not an exact integer Goal Top3 member.",
            "Draw-sufficient and friendly substitutions are timestamped context reviews, not new prediction factors or odds transformations.",
            "No automated formal direction, core, protection, handicap, goal or score authorization.",
        ],
    }
