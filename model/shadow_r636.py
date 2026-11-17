"""Shadow R6.3.6: protection ambiguity, exact 0/5 tail, score-family and handicap audits.

Research-only overlay on M79.3.6 Production + Shadow R6.3.5.
No fitted weights, WDL probability changes, direction flips, or formal grants.
All prematch evidence must be timestamped before the frozen cutoff.
Post-match recap replay is descriptive only and cannot be passed to inspect().
"""
from __future__ import annotations

from typing import Any
import math
import shadow_r635 as r635
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.6_20261108"
WDL = ("胜", "平", "负")
HTFT = r635.HTFT_STATES
GOAL_BUCKETS = r635.GOAL_BUCKETS
TAIL_FAMILIES = {"attacking_profile", "defensive_instability", "pace_transition",
                 "lineup_bench", "market_ou", "set_piece_profile"}
EXACT_TAIL_BUCKETS = {"0", "5", "7+"}


def _rank_wdl(p: list[float]) -> list[int]:
    return sorted(range(3), key=lambda i: (-p[i], i))


def _validate_pair(pair: Any, label: str) -> list[str]:
    if (not isinstance(pair, list) or len(pair) != 2 or len(set(pair)) != 2
            or not set(pair).issubset(WDL)):
        raise ValueError(f"{label} must contain two distinct WDL outcomes")
    return list(pair)


def _protection_v02(packet: dict, probabilities: list[float], score_audit: dict) -> dict:
    """Do not auto-authorize a protection when the 2nd/3rd WDL outcomes tie.

    A top-3 exact-score draw cluster that conflicts with a proposed pair excluding
    draw triggers manual review only; exact-score ranks never override WDL marginals.
    """
    ranked = _rank_wdl(probabilities)
    raw_top1 = WDL[ranked[0]]
    candidate = [WDL[i] for i in ranked[:2]]
    gap = probabilities[ranked[1]] - probabilities[ranked[2]]
    tie = gap <= 0.0100001
    prior = packet.get("previous_research_protection")
    prior_valid = None
    if prior is not None:
        prior_valid = _validate_pair(prior, "previous_research_protection")
        if raw_top1 not in prior_valid:
            raise ValueError("previous research protection must include raw Top1")

    if tie and prior_valid is not None:
        proposed = prior_valid
        status = "MANUAL_REVIEW_KEEP_PRIOR_PAIR"
        candidate_release = False
    elif tie:
        proposed = candidate
        status = "MANUAL_REVIEW_NO_PRIOR_PAIR"
        candidate_release = False
    else:
        proposed = candidate
        status = "CLEAR_RANK_ORDER_SHADOW_ONLY"
        candidate_release = True

    cross_flags = []
    if score_audit.get("status") == "JOINT_MATRIX_COHERENT":
        top3 = score_audit.get("score_top3", [])
        draw_top3 = sum(1 for s in top3 if int(s.split(":")[0]) == int(s.split(":")[1]))
        if "平" not in proposed and (draw_top3 >= 2 or (top3 and top3[0].split(":")[0] == top3[0].split(":")[1])):
            cross_flags.append("DRAW_SCORE_FAMILY_CONFLICTS_WITH_PROTECTION_PAIR")
        if cross_flags:
            status = "MANUAL_REVIEW_CROSS_LAYER_CONFLICT"
            candidate_release = False

    return {
        "version": "Protection_v0.2",
        "rule": "RAW_TOP1_PLUS_HIGHEST_REMAINING_WDL_PROBABILITY",
        "raw_top1": raw_top1,
        "research_candidate_pair": proposed,
        "research_proposed_protection": proposed if candidate_release else None,
        "candidate_pair_for_manual_review": proposed if not candidate_release else None,
        "previous_research_protection": prior_valid,
        "second_vs_third_probability_gap": round(gap, 6),
        "tie_or_rounding_ambiguity": tie,
        "cross_layer_flags": cross_flags,
        "status": status,
        "formal_protection_grant": None,
        "probability_adjustment": False,
        "automatic_pair_change": False,
    }


def _exact_tail_route(packet: dict, base_tail: dict) -> dict:
    """One exact bucket (0, 5 or 7+) can compete for one tail slot with 2 families.

    If exact-bucket evidence conflicts with RC2.4's already selected different tail,
    keep the original Top3 rather than spending two tail slots.
    """
    raw_dist = packet.get("goal_distribution")
    if raw_dist is None:
        return {"version": "RC2.5", "status": "UNKNOWN_NO_GOAL_DISTRIBUTION",
                "shadow_top3": None, "tail_slots_used": 0, "probability_adjustment": False}
    dist = r635._normalise_distribution(raw_dist, GOAL_BUCKETS, "goal_distribution")
    base_top3 = list(base_tail.get("base_top3") or sorted(GOAL_BUCKETS, key=lambda k: (-dist[k], GOAL_BUCKETS.index(k)))[:3])
    central = base_top3[0]
    evidence = packet.get("exact_tail_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("exact_tail_evidence must be a list")

    # Do not let the same causal family vote once in RC2.4 and again here.
    broad_families = {x.get("family") for x in packet.get("tail_evidence", []) if isinstance(x, dict)}
    seen: set[str] = set()
    support: dict[str, set[str]] = {b: set() for b in EXACT_TAIL_BUCKETS}
    cutoff = base._time(packet["cutoff"], "cutoff")
    for rec in evidence:
        if not isinstance(rec, dict):
            raise ValueError("exact_tail_evidence item must be an object")
        family, bucket = rec.get("family"), rec.get("bucket")
        if family not in TAIL_FAMILIES:
            raise ValueError("unsupported exact-tail evidence family")
        if bucket not in EXACT_TAIL_BUCKETS:
            raise ValueError("exact-tail bucket must be 0, 5 or 7+")
        if family in seen or family in broad_families:
            raise ValueError("correlated tail evidence family counted more than once")
        seen.add(family)
        r635._timestamp(rec, f"exact_tail_evidence.{family}", cutoff)
        support[bucket].add(family)

    triggered = [b for b, families in support.items() if len(families) >= 2]
    if len(triggered) > 1:
        return {"version": "RC2.5", "status": "EXACT_TAIL_CONFLICT_KEEP_BASE",
                "base_top3": base_top3, "shadow_top3": base_top3,
                "supported_buckets": triggered, "support_families": {k: sorted(v) for k,v in support.items()},
                "tail_slots_used": int(base_tail.get("tail_slots_used", 0)),
                "probability_adjustment": False}
    if not triggered:
        return {"version": "RC2.5", "status": "NO_TWO_FAMILY_EXACT_BUCKET_TRIGGER",
                "base_top3": base_top3, "shadow_top3": base_tail.get("shadow_top3") or base_top3,
                "supported_buckets": [], "support_families": {k: sorted(v) for k,v in support.items()},
                "tail_slots_used": int(base_tail.get("tail_slots_used", 0)),
                "probability_adjustment": False}

    target = triggered[0]
    existing_slot = base_tail.get("tail_slot")
    base_slots = int(base_tail.get("tail_slots_used", 0))
    if base_tail.get("status") == "BOTH_TAILS_CONFLICT_KEEP_BASE":
        return {"version": "RC2.5", "status": "BROAD_TAIL_CONFLICT_KEEP_BASE",
                "base_top3": base_top3, "shadow_top3": base_top3,
                "supported_buckets": triggered, "tail_slots_used": 0,
                "probability_adjustment": False}
    if base_slots and existing_slot != target and target not in base_top3:
        return {"version": "RC2.5", "status": "EXACT_VS_BROAD_TAIL_CONFLICT_KEEP_BASE",
                "base_top3": base_top3, "shadow_top3": base_top3,
                "broad_tail_slot": existing_slot, "exact_tail_bucket": target,
                "tail_slots_used": base_slots, "probability_adjustment": False}

    if target in base_top3:
        shadow = base_top3
        status = "EXACT_TAIL_ALREADY_IN_TOP3"
        slots = base_slots
    else:
        shadow = [central, target]
        for b in sorted(GOAL_BUCKETS, key=lambda k: (-dist[k], GOAL_BUCKETS.index(k))):
            if b not in shadow:
                shadow.append(b)
            if len(shadow) == 3:
                break
        status = "EXACT_BUCKET_ONE_SLOT"
        slots = 1
    return {"version": "RC2.5", "status": status,
            "base_top3": base_top3, "shadow_top3": shadow,
            "central_peak": central, "exact_tail_bucket": target,
            "support_families": {k: sorted(v) for k,v in support.items()},
            "tail_slots_used": slots, "probability_adjustment": False}


def _score_family_audit(packet: dict, score_audit: dict, exact_tail: dict) -> dict:
    """Keep probability-ranked Score Top3; add family diagnostics, never re-rank it."""
    matrix = packet.get("score_matrix")
    if not matrix or score_audit.get("status") != "JOINT_MATRIX_COHERENT":
        return {"version": "GS1.4", "status": "UNKNOWN_NO_COHERENT_SCORE_MATRIX",
                "score_top3": None, "family_watch_candidates": None,
                "probability_adjustment": False}
    ordered = sorted(matrix, key=lambda x: (-float(x["probability"]), x["score"]))
    top3 = ordered[:3]
    result_counts = {"胜": 0, "平": 0, "负": 0}
    total_counts: dict[str, int] = {}
    for row in top3:
        h, a = (int(x) for x in row["score"].split(":"))
        result = "胜" if h > a else "平" if h == a else "负"
        result_counts[result] += 1
        total = str(h+a) if h+a <= 6 else "7+"
        total_counts[total] = total_counts.get(total, 0) + 1
    family_watch = {}
    for outcome in ("胜", "平", "负"):
        candidates = []
        for row in matrix:
            h, a = (int(x) for x in row["score"].split(":"))
            label = "胜" if h > a else "平" if h == a else "负"
            if label == outcome:
                candidates.append(row)
        if candidates:
            best = max(candidates, key=lambda x: (float(x["probability"]), x["score"]))
            family_watch[outcome] = {"score": best["score"], "probability": float(best["probability"])}
    flags = []
    if max(result_counts.values()) == 3:
        flags.append("SCORE_TOP3_SINGLE_WDL_FAMILY_CONCENTRATION")
    if len(total_counts) == 1:
        flags.append("SCORE_TOP3_SINGLE_TOTAL_GOAL_BUCKET_CONCENTRATION")
    exact_target = exact_tail.get("exact_tail_bucket")
    top_total_buckets = set()
    for score in (x["score"] for x in top3):
        h, a = (int(v) for v in score.split(":"))
        total = h + a
        top_total_buckets.add(str(total) if total <= 6 else "7+")
    if exact_tail.get("status") == "EXACT_BUCKET_ONE_SLOT" and exact_target not in top_total_buckets:
        flags.append("EXACT_TAIL_GOAL_BUCKET_NOT_REPRESENTED_IN_SCORE_TOP3")
    return {"version": "GS1.4", "status": "SCORE_FAMILY_AUDITED",
            "score_top3": [x["score"] for x in top3],
            "score_top3_result_counts": result_counts,
            "score_top3_total_goal_counts": total_counts,
            "family_watch_candidates": family_watch,
            "flags": flags,
            "ranking_changed": False, "probability_adjustment": False}


def _handicap_audit(packet: dict, probabilities: list[float]) -> dict:
    """S4 v1.6 derives integer handicap probabilities from the joint score matrix."""
    matrix = packet.get("score_matrix")
    line = packet.get("home_handicap_line")
    if matrix is None or line is None:
        return {"version": "S4_v1.6", "status": "UNKNOWN_NO_SCORE_MATRIX_OR_HANDICAP_LINE",
                "handicap_probabilities": None, "formal_handicap_grant": None}
    if type(line) is not int or line < -3 or line > 3:
        raise ValueError("home_handicap_line must be an integer from -3 to +3")
    mass = sum(float(r["probability"]) for r in matrix)
    if not math.isclose(mass, 1.0, abs_tol=.002):
        raise ValueError("score_matrix probabilities must sum to 1")
    out = {"让胜": 0.0, "让平": 0.0, "让负": 0.0}
    margins = {"home_margin_1": 0.0, "home_margin_2plus": 0.0,
               "draw": 0.0, "away_margin_1": 0.0, "away_margin_2plus": 0.0}
    for row in matrix:
        h, a = (int(x) for x in row["score"].split(":"))
        p = float(row["probability"])
        adjusted = h + line - a
        outcome = "让胜" if adjusted > 0 else "让平" if adjusted == 0 else "让负"
        out[outcome] += p
        if h-a == 1: margins["home_margin_1"] += p
        elif h-a >= 2: margins["home_margin_2plus"] += p
        elif h == a: margins["draw"] += p
        elif a-h == 1: margins["away_margin_1"] += p
        else: margins["away_margin_2plus"] += p
    ranked = sorted(out, key=lambda k: (-out[k], ("让胜","让平","让负").index(k)))
    gap = out[ranked[0]] - out[ranked[1]]
    close = gap <= .0100001
    return {"version": "S4_v1.6", "status": "MANUAL_REVIEW_CLOSE_HANDICAP_OUTCOMES" if close else "JOINT_MATRIX_HANDICAP_AUDITED",
            "home_handicap_line": line,
            "handicap_probabilities": {k: round(v, 6) for k,v in out.items()},
            "research_top1": ranked[0] if not close else None,
            "candidate_top2_for_review": ranked[:2] if close else None,
            "top1_top2_gap": round(gap, 6),
            "net_margin_probabilities": {k: round(v,6) for k,v in margins.items()},
            "probability_adjustment": False, "formal_handicap_grant": None}


def _selection_efficiency_v04(packet: dict, parent: dict, hfrg: dict, protection: dict) -> dict:
    p = parent["outcome_probabilities_unchanged"]
    ranked = _rank_wdl(p)
    top1, second, third = (p[i] for i in ranked)
    gap = top1 - second
    level = packet.get("research_selection_level")
    if level not in (None, "core_candidate", "hot_favorite_review", "observation", "avoid", "核心候选", "热门二审", "观察", "规避"):
        raise ValueError("unsupported research_selection_level")
    if top1 < .40 or gap <= .03:
        direction_state = "WEAK_EDGE_DIRECTION_ONLY"
    elif top1 >= .60 and gap >= .15:
        direction_state = "STRONG_DIRECTION_REVIEW"
    elif top1 >= .50 and gap >= .05:
        direction_state = "MODERATE_DIRECTION_REVIEW"
    else:
        direction_state = "NARROW_EDGE_DIRECTION_ONLY"
    avoid = level in ("avoid", "规避")
    recovery_review = avoid and top1 >= .35 and gap <= .08
    if recovery_review and hfrg.get("status", "").startswith("HIGH_RISK"):
        recovery_status = "KEEP_HOLD_HIGH_RISK_NOT_RECOVERY"
    elif recovery_review:
        recovery_status = "REVIEW_AVOIDED_TOP1_OPPORTUNITY_NO_AUTO_RESTORE"
    else:
        recovery_status = "NO_AVOIDANCE_RECOVERY_TRIGGER"
    return {"version": "Selection_Efficiency_v0.4", "raw_direction": WDL[ranked[0]],
            "top1_probability": round(top1,6), "top1_minus_second_gap": round(gap,6),
            "direction_state": direction_state, "research_selection_level": level,
            "avoidance_recovery_review": recovery_status,
            "protection_manual_review": protection["status"].startswith("MANUAL_REVIEW"),
            "formal_single_grant": None, "probability_adjustment": False,
            "automatic_direction_flip": False}


def inspect(packet: dict) -> dict:
    """Run inherited R6.3.5 then the R6.3.6 shadow-only audit overlays."""
    parent = r635.inspect(packet)
    probabilities = parent["outcome_probabilities_unchanged"]
    score_audit = parent["GS1_3_joint_score_audit"]
    protection = _protection_v02(packet, probabilities, score_audit)
    exact_tail = _exact_tail_route(packet, parent["RC2_4_tail_router"])
    score_family = _score_family_audit(packet, score_audit, exact_tail)
    handicap = _handicap_audit(packet, probabilities)
    selection = _selection_efficiency_v04(packet, parent, parent["HFRG_home_favorite_risk_gate"], protection)
    ht = parent["HT_State_v0_2"]
    ht_v03 = {"version": "HT_State_v0.3", **ht,
              "formal_top2_grant": None,
              "top2_release_status": "RESEARCH_ONLY_JOINT_MATRIX_REQUIRED" if ht.get("status") == "HALF_FULL_MARGINAL_COHERENT" else "NO_TOP2_RELEASE_MISSING_JOINT_MATRIX",
              "fallback_from_score_top3_forbidden": True}
    flags = list(parent.get("audit_flags_r635", []))
    flags.extend(protection.get("cross_layer_flags", []))
    flags.extend(score_family.get("flags", []))
    if protection["status"].startswith("MANUAL_REVIEW"):
        flags.append("PROTECTION_V02_MANUAL_REVIEW_NO_AUTO_PAIR")
    if exact_tail["status"] in ("EXACT_TAIL_CONFLICT_KEEP_BASE", "EXACT_VS_BROAD_TAIL_CONFLICT_KEEP_BASE", "BROAD_TAIL_CONFLICT_KEEP_BASE"):
        flags.append("RC2_5_EXACT_TAIL_CONFLICT_KEEP_BASE")
    if handicap["status"] == "MANUAL_REVIEW_CLOSE_HANDICAP_OUTCOMES":
        flags.append("S4_V16_HANDICAP_CLOSE_OUTCOMES_REVIEW")
    return {**parent, "version": VERSION,
            "Protection_v0_2": protection,
            "RC2_5_exact_bucket_router": exact_tail,
            "GS1_4_score_family_audit": score_family,
            "S4_v1_6_joint_handicap_audit": handicap,
            "Selection_Efficiency_v0_4": selection,
            "HT_State_v0_3": ht_v03,
            "audit_flags_r636": flags,
            "outcome_probabilities_unchanged": probabilities,
            "probability_adjustment_applied": False,
            "automatic_direction_flip": False,
            "formal_single_grant": None,
            "formal_core_grant": None,
            "formal_protection_grant": None,
            "formal_handicap_grant": None,
            "production_changed": False,
            "notes_r636": [
                "Production M79.3.6 remains frozen; R6.3.6 is Shadow only.",
                "A <=1pp second/third WDL tie is manual review; without a prior valid pair no protection pair is released.",
                "Exact 0/5/7+ goal buckets require two independent precutoff evidence families and can use at most one tail slot.",
                "Score family watch candidates supplement but never replace probability-ranked Score Top3.",
                "Integer handicap probabilities are aggregated from the same joint score matrix; close outcomes are held for review.",
                "Half/full Top2 is released only when the complete joint distribution reconciles to WDL.",
                "No actual result, in-play event or post-cutoff feature is permitted in prematch inspect()."]}


def replay_batch14(rows: list[dict]) -> dict:
    """Descriptive replay of the 14-row prior-conversation recap; never a holdout or fit set."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows required")
    ids = set()
    metrics = {k: 0 for k in ("single", "protection", "handicap", "goals_top3", "score_top3", "half_full_top2")}
    levels: dict[str, dict[str,int]] = {}
    per = []
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str) or rid in ids:
            raise ValueError("each recap row needs a unique id")
        ids.add(rid)
        actual_score = row.get("actual_score")
        ht_score = row.get("half_time_score")
        if (not isinstance(actual_score,list) or len(actual_score)!=2 or any(type(x) is not int or x<0 for x in actual_score)
                or not isinstance(ht_score,list) or len(ht_score)!=2 or any(type(x) is not int or x<0 for x in ht_score)):
            raise ValueError("actual_score and half_time_score must be nonnegative integer pairs")
        actual = "胜" if actual_score[0]>actual_score[1] else "平" if actual_score[0]==actual_score[1] else "负"
        ht = "胜" if ht_score[0]>ht_score[1] else "平" if ht_score[0]==ht_score[1] else "负"
        actual_htft = ht + actual
        p = base._p3(row.get("probabilities"))
        ranked = _rank_wdl(list(p)); raw = WDL[ranked[0]]
        protected = _validate_pair(row.get("protection"), "protection")
        if raw not in protected:
            raise ValueError("protection pair must include the raw unique direction")
        actual_total = sum(actual_score)
        goal_top3 = row.get("goal_top3")
        score_top3 = row.get("score_top3")
        htft_top2 = row.get("half_full_top2")
        if not isinstance(goal_top3,list) or len(goal_top3)!=3 or any(str(x) not in GOAL_BUCKETS for x in goal_top3):
            raise ValueError("goal_top3 must contain three valid goal buckets")
        if not isinstance(score_top3,list) or len(score_top3)!=3 or any(not isinstance(x,str) for x in score_top3):
            raise ValueError("score_top3 must contain three score strings")
        if not isinstance(htft_top2,list) or len(htft_top2)!=2 or any(x not in HTFT for x in htft_top2):
            raise ValueError("half_full_top2 must contain two HTFT states")
        line = row.get("home_handicap_line")
        pick = row.get("handicap_pick")
        if type(line) is not int or pick not in ("让胜","让平","让负"):
            raise ValueError("home_handicap_line and handicap_pick required")
        adjusted = actual_score[0] + line - actual_score[1]
        actual_handicap = "让胜" if adjusted>0 else "让平" if adjusted==0 else "让负"
        level = row.get("research_level", "unclassified")
        flags = {
            "single": raw == actual,
            "protection": actual in protected,
            "handicap": pick == actual_handicap,
            "goals_top3": str(actual_total) in goal_top3 if actual_total <= 6 else "7+" in goal_top3,
            "score_top3": f"{actual_score[0]}:{actual_score[1]}" in score_top3,
            "half_full_top2": actual_htft in htft_top2,
        }
        for k,v in flags.items(): metrics[k] += int(v)
        lv = levels.setdefault(level,{"n":0,"raw_top1_hits":0,"avoided_correct_top1":0})
        lv["n"] += 1; lv["raw_top1_hits"] += int(flags["single"])
        if level in ("avoid","规避") and flags["single"]: lv["avoided_correct_top1"] += 1
        per.append({"id":rid,"raw_direction":raw,"actual_wdl":actual,"actual_score":f"{actual_score[0]}:{actual_score[1]}",
                    "actual_htft":actual_htft,"actual_total_goals":actual_total,
                    "actual_handicap":actual_handicap,"predicted_handicap":pick,
                    "hits":flags,"research_level":level})
    n=len(rows)
    summary={k:{"hits":v,"n":n,"rate":v/n} for k,v in metrics.items()}
    return {"version":VERSION,"dataset":"PRIOR_CONVERSATION_RECAP_ONLY_NOT_OFFICIALLY_FROZEN_NOT_HOLDOUT",
            "n":n,"metrics":summary,"research_levels":levels,
            "correct_top1_in_avoidance_groups":sum(x["avoided_correct_top1"] for x in levels.values()),
            "avoidance_group_n":sum(x["n"] for k,x in levels.items() if k in ("avoid","规避")),
            "training_or_threshold_fit":False,"independent_validation":False,
            "proper_probability_scores":None,
            "notes":["Descriptive arithmetic only; source rows came from prior conversation recap.",
                     "Do not fit thresholds or claim independent performance from this batch.",
                     "Actual outcomes are joined only after the prematch predictions in each row are frozen."],
            "rows":per}
