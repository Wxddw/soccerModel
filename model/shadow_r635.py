"""Shadow R6.3.5: home-favorite risk, dynamic protection and joint tail audits.

Research-only overlay on R6.3.4. It does not fit weights, alter W/D/L
probabilities, flip a direction, or issue a formal single/core grant.
All evidence must be timestamped before the frozen pre-match cutoff.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
import math

import motivation_squad_r634 as r634
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.5_20261106"
WDL = ("胜", "平", "负")
GOAL_BUCKETS = ("0", "1", "2", "3", "4", "5", "6", "7+")
LOW_BUCKETS = {"0", "1"}
HIGH_BUCKETS = {"4", "5", "6", "7+"}
HTFT_STATES = ("胜胜", "胜平", "胜负", "平胜", "平平", "平负", "负胜", "负平", "负负")

# HFRG uses independent evidence families, not raw signal counts.
_RISK_GROUP = {
    "roster": "roster", "injury": "roster", "official_lineup": "roster",
    "goalkeeper": "roster", "defensive_spine": "roster", "bench_quality": "roster",
    "schedule": "schedule", "rotation": "schedule", "short_turnaround": "schedule",
    "tactical_matchup": "tactical", "opponent_transition": "tactical",
    "set_piece_matchup": "tactical", "coach_transition": "tactical",
    "market_price": "market", "market_flow": "market", "kelly": "market",
}


def _timestamp(value: Any, label: str, cutoff: datetime) -> tuple[str, datetime]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a source record")
    sid = value.get("source_id")
    if not isinstance(sid, str) or not sid.strip():
        raise ValueError(f"{label}.source_id required")
    dt = base._time(value.get("observed_at"), f"{label}.observed_at")
    if dt > cutoff:
        raise ValueError(f"{label} is post-cutoff")
    return sid, dt


def _normalise_distribution(raw: Any, keys: tuple[str, ...], label: str) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise ValueError(f"{label} must contain exactly {list(keys)}")
    out = {}
    for k in keys:
        v = raw[k]
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 1:
            raise ValueError(f"{label}.{k} must be a finite probability")
        out[k] = float(v)
    if not math.isclose(sum(out.values()), 1.0, abs_tol=.002):
        raise ValueError(f"{label} must sum to 1")
    total = sum(out.values())
    return {k: v / total for k, v in out.items()}


def _risk_audit(packet: dict, probabilities: list[float], squad: dict) -> dict:
    """HFRG: review home favorites only; no probability or direction change.

    HIGH_RISK_REVIEW requires either a severe pre-match critical-spine downgrade
    or >=2 adverse independent families. One adverse family => WATCH. Fewer than
    two independently audited families => UNKNOWN, never interpreted as safe.
    """
    raw_i = max(range(3), key=lambda i: (probabilities[i], -i))
    is_home_favorite = raw_i == 0 and probabilities[0] >= .50
    if not is_home_favorite:
        return {"status": "NOT_APPLICABLE_NOT_HOME_FAVORITE", "home_favorite": False,
                "independent_families": {}, "adverse_family_count": 0,
                "critical_spine_severe": False, "probability_adjustment": False}

    cutoff = base._time(packet["cutoff"], "cutoff")
    records = packet.get("risk_evidence")
    if records is None:
        records = []
    if not isinstance(records, list):
        raise ValueError("risk_evidence must be a list")
    families: dict[str, dict] = {}
    for rec in records:
        if not isinstance(rec, dict):
            raise ValueError("risk_evidence item must be an object")
        family = rec.get("family")
        if family not in _RISK_GROUP:
            raise ValueError(f"unsupported risk evidence family: {family}")
        group = _RISK_GROUP[family]
        if group in families:
            raise ValueError(f"correlated risk evidence duplicated within {group}")
        sid, dt = _timestamp(rec, f"risk_evidence.{family}", cutoff)
        state = rec.get("state")
        if state not in ("adverse_to_home", "neutral", "favorable_to_home"):
            raise ValueError("risk evidence state must be adverse_to_home/neutral/favorable_to_home")
        severe = rec.get("critical_spine_severe", False)
        if type(severe) is not bool:
            raise ValueError("critical_spine_severe must be boolean")
        families[group] = {"source_id": sid, "observed_at": dt.isoformat(),
                           "state": state, "critical_spine_severe": severe}

    # Derive a role-specific severe warning from R6.3.4 ESR if the complete squad
    # matrix exists. This is still one roster family, not another independent vote.
    esr_critical = False
    esr_flags: list[str] = []
    if squad.get("status") in ("CONFIRMED_BOTH", "PROJECTED_AT_LEAST_ONE"):
        for side in ("home", "away"):
            role = squad["sides"][side].get("role_contributions", {})
            gk = role.get("goalkeeper")
            cb_dm = float(role.get("center_back", 0.0)) + float(role.get("defensive_midfielder", 0.0))
            attack = (float(role.get("attacking_midfielder", 0.0)) +
                      float(role.get("winger", 0.0)) + float(role.get("striker", 0.0)))
            if side == "home" and gk is not None and gk <= -0.75:
                esr_critical = True; esr_flags.append("HOME_GOALKEEPER_QUALITY_DROP")
            if side == "home" and cb_dm <= -1.50:
                esr_critical = True; esr_flags.append("HOME_CENTRAL_DEFENSIVE_SPINE_DROP")
            if side == "home" and attack <= -1.50:
                esr_flags.append("HOME_ATTACKING_UNIT_QUALITY_DROP")
            if side == "away" and gk is not None and gk <= -0.75:
                esr_flags.append("AWAY_GOALKEEPER_QUALITY_DROP_MAY_SUPPORT_HOME")
    roster = families.get("roster")
    explicit_critical = bool(roster and roster["critical_spine_severe"] and roster["state"] == "adverse_to_home")
    critical = explicit_critical or esr_critical
    adverse = sum(v["state"] == "adverse_to_home" for v in families.values())
    favorable = sum(v["state"] == "favorable_to_home" for v in families.values())
    if critical:
        status = "HIGH_RISK_REVIEW_CRITICAL_SPINE"
    elif adverse >= 2:
        status = "HIGH_RISK_REVIEW_TWO_INDEPENDENT_FAMILIES"
    elif adverse == 1:
        status = "WATCH_ONE_ADVERSE_FAMILY"
    elif len(families) < 2:
        status = "UNKNOWN_INSUFFICIENT_INDEPENDENT_RISK_AUDIT"
    else:
        status = "NO_HFRG_TRIGGER_REVIEWED"
    return {"status": status, "home_favorite": True,
            "independent_families": families, "independent_family_count": len(families),
            "adverse_family_count": adverse, "favorable_family_count": favorable,
            "critical_spine_severe": critical, "esr_role_flags": esr_flags,
            "minimum_independent_families_for_clear_review": 2,
            "probability_adjustment": False, "automatic_direction_flip": False,
            "authorization_effect": "HOLD_CORE_REVIEW" if status.startswith("HIGH_RISK") else
                "WATCH" if status.startswith("WATCH") or status.startswith("UNKNOWN") else "NO_EXTRA_HFRG_HOLD"}


def _protection_audit(packet: dict, probabilities: list[float]) -> dict:
    ranked = sorted(range(3), key=lambda i: (-probabilities[i], i))
    proposed = [WDL[i] for i in ranked[:2]]
    gap_second_third = probabilities[ranked[1]] - probabilities[ranked[2]]
    tie = gap_second_third <= .0100001  # rounded input may hide a meaningful ordering
    prior = packet.get("previous_research_protection")
    if prior is not None:
        if (not isinstance(prior, list) or len(prior) != 2 or len(set(prior)) != 2
                or not set(prior).issubset(WDL)):
            raise ValueError("previous_research_protection must be two distinct WDL outcomes")
        raw = WDL[ranked[0]]
        if raw not in prior:
            raise ValueError("previous research protection must include raw Top1")
        # A rounded tie is not a license to invent precision. Preserve the prior
        # valid pair as the tie-break and mark it for manual review.
        if tie:
            proposed = list(prior)
    return {"rule": "RAW_TOP1_PLUS_HIGHEST_REMAINING_WDL_PROBABILITY; KEEP_VALID_PRIOR_PAIR_ON_ROUNDED_TIE",
            "research_proposed_protection": proposed,
            "previous_research_protection": prior,
            "changed_vs_previous": bool(prior is not None and set(prior) != set(proposed)),
            "second_vs_third_probability_gap": round(gap_second_third, 6),
            "second_slot_tie_or_rounding_ambiguity": tie,
            "tie_status": "MANUAL_REVIEW_KEEP_FROZEN_PAIR" if tie else "CLEAR_RANK_ORDER",
            "frozen_protection_unchanged": packet.get("frozen_protection"),
            "formal_protection_grant": None}


def _tail_route(packet: dict) -> dict:
    raw = packet.get("goal_distribution")
    if raw is None:
        return {"status": "UNKNOWN_NO_INTEGER_GOAL_DISTRIBUTION", "base_top3": None,
                "shadow_top3": None, "probability_adjustment": False}
    dist = _normalise_distribution(raw, GOAL_BUCKETS, "goal_distribution")
    base_top3 = sorted(GOAL_BUCKETS, key=lambda k: (-dist[k], GOAL_BUCKETS.index(k)))[:3]
    cutoff = base._time(packet["cutoff"], "cutoff")
    evidence = packet.get("tail_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("tail_evidence must be a list")
    seen: set[str] = set(); high: set[str] = set(); low: set[str] = set()
    for rec in evidence:
        if not isinstance(rec, dict): raise ValueError("tail_evidence item must be object")
        family = rec.get("family")
        if family not in {"attacking_profile", "defensive_instability", "pace_transition",
                          "lineup_bench", "market_ou", "set_piece_profile"}:
            raise ValueError(f"unsupported tail evidence family: {family}")
        if family in seen: raise ValueError("duplicate correlated tail evidence family")
        seen.add(family)
        _timestamp(rec, f"tail_evidence.{family}", cutoff)
        direction = rec.get("direction")
        if direction not in ("high", "low", "neutral"): raise ValueError("tail direction must be high/low/neutral")
        if direction == "high": high.add(family)
        elif direction == "low": low.add(family)
    central = base_top3[0]
    high_trigger = len(high) >= 2
    low_trigger = len(low) >= 2
    if high_trigger and low_trigger:
        return {"status": "BOTH_TAILS_CONFLICT_KEEP_BASE", "base_top3": base_top3,
                "shadow_top3": base_top3, "central_peak": central,
                "high_evidence_families": sorted(high), "low_evidence_families": sorted(low),
                "tail_slots_used": 0, "probability_adjustment": False}
    if not high_trigger and not low_trigger:
        return {"status": "NO_TWO_FAMILY_TAIL_TRIGGER_KEEP_BASE", "base_top3": base_top3,
                "shadow_top3": base_top3, "central_peak": central,
                "high_evidence_families": sorted(high), "low_evidence_families": sorted(low),
                "tail_slots_used": 0, "probability_adjustment": False}
    target = HIGH_BUCKETS if high_trigger else LOW_BUCKETS
    target_sorted = sorted(target, key=lambda k: (-dist[k], GOAL_BUCKETS.index(k)))
    # The central peak itself may already be the tail bucket; otherwise reserve
    # exactly one slot for the best supported tail bucket.
    tail_slot = central if central in target else target_sorted[0]
    chosen = [central]
    if tail_slot not in chosen: chosen.append(tail_slot)
    for k in sorted(GOAL_BUCKETS, key=lambda x: (-dist[x], GOAL_BUCKETS.index(x))):
        if k not in chosen:
            chosen.append(k)
        if len(chosen) == 3: break
    return {"status": "HIGH_TAIL_ONE_SLOT" if high_trigger else "LOW_TAIL_ONE_SLOT",
            "base_top3": base_top3, "shadow_top3": chosen,
            "central_peak": central, "tail_slot": tail_slot,
            "high_evidence_families": sorted(high), "low_evidence_families": sorted(low),
            "tail_slots_used": 1,
            "probabilities_unchanged": True, "probability_adjustment": False}


def _score_matrix_audit(packet: dict, probabilities: list[float], goal_dist: dict | None) -> dict:
    raw = packet.get("score_matrix")
    if raw is None:
        return {"status": "UNKNOWN_NO_JOINT_SCORE_MATRIX", "score_top3": None,
                "probability_adjustment": False}
    if not isinstance(raw, list) or not raw:
        raise ValueError("score_matrix must be a non-empty list")
    scores: dict[str, float] = {}
    wdl = [0.0, 0.0, 0.0]
    goals = {k: 0.0 for k in GOAL_BUCKETS}
    families = {"low_event_0_1": 0.0, "central_2_3": 0.0, "high_4_plus": 0.0,
                "home_narrow_1": 0.0, "home_multi_2_plus": 0.0,
                "draw": 0.0, "away_narrow_1": 0.0, "away_multi_2_plus": 0.0}
    for row in raw:
        if not isinstance(row, dict): raise ValueError("score_matrix row must be object")
        score = row.get("score")
        prob = row.get("probability")
        if not isinstance(score, str) or score.count(":") != 1:
            raise ValueError("score must be H:A string")
        try: h, a = (int(x) for x in score.split(":"))
        except Exception as e: raise ValueError("score must contain integer goals") from e
        if h < 0 or a < 0 or h > 10 or a > 10: raise ValueError("score goals must be 0..10")
        if score in scores: raise ValueError("duplicate scoreline")
        if type(prob) not in (int, float) or not math.isfinite(prob) or prob < 0 or prob > 1:
            raise ValueError("score probability invalid")
        scores[score] = float(prob)
        idx = 0 if h > a else 1 if h == a else 2
        wdl[idx] += float(prob)
        total = h + a
        bucket = str(total) if total <= 6 else "7+"
        goals[bucket] += float(prob)
        if total <= 1: families["low_event_0_1"] += float(prob)
        elif total <= 3: families["central_2_3"] += float(prob)
        else: families["high_4_plus"] += float(prob)
        if h > a:
            families["home_narrow_1" if h-a == 1 else "home_multi_2_plus"] += float(prob)
        elif h == a: families["draw"] += float(prob)
        else:
            families["away_narrow_1" if a-h == 1 else "away_multi_2_plus"] += float(prob)
    total_mass = sum(scores.values())
    if not math.isclose(total_mass, 1.0, abs_tol=.002):
        raise ValueError("score_matrix probabilities must sum to 1")
    if any(abs(wdl[i] - probabilities[i]) > .015 for i in range(3)):
        raise ValueError("score_matrix WDL marginal does not match Outcome probabilities (tolerance 1.5pp)")
    goal_gap = None
    if goal_dist is not None:
        goal_gap = max(abs(goals[k] - goal_dist[k]) for k in GOAL_BUCKETS)
        if goal_gap > .015:
            raise ValueError("score_matrix goal marginal does not match goal_distribution (tolerance 1.5pp)")
    top3 = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return {"status": "JOINT_MATRIX_COHERENT", "score_top3": [k for k, _ in top3],
            "score_top3_probabilities": [v for _, v in top3],
            "wdl_marginals": wdl, "goal_marginal_max_gap": goal_gap,
            "score_families": families, "probability_adjustment": False}


def _ht_state_audit(packet: dict, probabilities: list[float]) -> dict:
    raw = packet.get("half_full_distribution")
    if raw is None:
        return {"status": "UNKNOWN_NO_HALF_FULL_DISTRIBUTION", "top2": None,
                "probability_adjustment": False}
    dist = _normalise_distribution(raw, HTFT_STATES, "half_full_distribution")
    ft = [sum(dist[s] for s in HTFT_STATES if s[1] == result) for result in ("胜", "平", "负")]
    if any(abs(ft[i] - probabilities[i]) > .015 for i in range(3)):
        raise ValueError("half/full distribution FT marginal does not match WDL probabilities")
    top2 = sorted(HTFT_STATES, key=lambda s: (-dist[s], HTFT_STATES.index(s)))[:2]
    return {"status": "HALF_FULL_MARGINAL_COHERENT", "top2": top2,
            "top2_probabilities": [dist[s] for s in top2], "full_time_marginals": ft,
            "probability_adjustment": False}


def inspect(packet: dict) -> dict:
    """Full R6.3.5 Shadow audit. All original WDL probabilities remain unchanged."""
    parent = r634.inspect(packet)
    probabilities = parent["outcome_probabilities_unchanged"]
    hfrg = _risk_audit(packet, probabilities, parent["effective_squad_ESR"])
    protection = _protection_audit(packet, probabilities)
    tail = _tail_route(packet)
    goal_dist = None
    if packet.get("goal_distribution") is not None:
        goal_dist = _normalise_distribution(packet["goal_distribution"], GOAL_BUCKETS, "goal_distribution")
    score = _score_matrix_audit(packet, probabilities, goal_dist)
    ht = _ht_state_audit(packet, probabilities)
    high_hfrg = hfrg["status"].startswith("HIGH_RISK")
    flags = []
    if high_hfrg: flags.append("HFRG_HOME_FAVORITE_HIGH_RISK_HOLD_CORE")
    if hfrg["status"].startswith("UNKNOWN"): flags.append("HFRG_RISK_AUDIT_INCOMPLETE_UNKNOWN_NOT_SAFE")
    if protection["second_slot_tie_or_rounding_ambiguity"]: flags.append("PROTECTION_SECOND_SLOT_TIE_REVIEW")
    if score["status"] == "UNKNOWN_NO_JOINT_SCORE_MATRIX": flags.append("GS_JOINT_MATRIX_MISSING")
    if score["status"] == "JOINT_MATRIX_COHERENT": flags.append("GS_JOINT_MATRIX_MARGINALS_COHERENT")
    if tail["status"] == "BOTH_TAILS_CONFLICT_KEEP_BASE": flags.append("RC_BOTH_TAILS_CONFLICT_KEEP_BASE")
    return {**parent, "version": VERSION,
            "HFRG_home_favorite_risk_gate": hfrg,
            "dynamic_protection_audit": protection,
            "RC2_4_tail_router": tail,
            "GS1_3_joint_score_audit": score,
            "HT_State_v0_2": ht,
            "r635_core_review_pass": bool(parent["research_core_context_review_pass"] and not high_hfrg
                                           and (not hfrg["home_favorite"] or
                                                hfrg["status"] == "NO_HFRG_TRIGGER_REVIEWED")),
            "r635_single_authorization_status": (
                "HOLD_SINGLE_AUTHORIZATION_REVIEW" if high_hfrg else
                "HOLD_RISK_AUDIT_INCOMPLETE" if hfrg["status"].startswith("UNKNOWN") and hfrg["home_favorite"] else
                "RETAIN_DIRECTION_WATCH" if hfrg["status"].startswith("WATCH") else
                "INHERIT_R634_RESEARCH_STATUS"),
            "audit_flags_r635": flags,
            "probability_adjustment_applied": False,
            "automatic_direction_flip": False,
            "formal_single_grant": None, "formal_core_grant": None,
            "production_changed": False,
            "notes_r635": [
                "HFRG only flags pre-match home-favorite risk; it never flips the unique direction or changes WDL probabilities.",
                "Protection is top1 plus the highest-probability remaining outcome; rounded ties require manual review.",
                "RC2.4 reserves at most one tail slot and preserves the central peak; two independent pre-cutoff evidence families are required.",
                "GS1.3 and HT-State must marginally reconcile to the same WDL/goal joint system.",
                "Unknown evidence is not low risk. No weights are fitted from the 13-match recap."]}


def replay_recap13(rows: list[dict]) -> dict:
    """Descriptive audit of the prior conversation recap; never a training/holdout set."""
    if not isinstance(rows, list) or not rows: raise ValueError("rows required")
    old_hit = new_hit = changed = tie_n = 0
    detail = []
    for row in rows:
        p = base._p3(row.get("probabilities"))
        ranked = sorted(range(3), key=lambda i: (-p[i], i))
        new_pair = [WDL[i] for i in ranked[:2]]
        old_pair = row.get("previous_protection")
        if not isinstance(old_pair, list) or len(old_pair) != 2 or row.get("actual") not in WDL:
            raise ValueError("recap row requires previous_protection and actual WDL")
        gap = p[ranked[1]] - p[ranked[2]]
        tie = gap <= .0100001
        if tie and WDL[ranked[0]] in old_pair:
            new_pair = list(old_pair)
        old_hit += row["actual"] in old_pair
        new_hit += row["actual"] in new_pair
        tie_n += tie
        changed += set(old_pair) != set(new_pair)
        detail.append({"id": row.get("id"), "old_protection": old_pair,
                       "dynamic_protection": new_pair, "actual": row["actual"],
                       "old_hit": row["actual"] in old_pair,
                       "dynamic_hit": row["actual"] in new_pair,
                       "second_slot_gap": round(gap, 4), "tie_review": tie})
    n = len(rows)
    return {"version": VERSION, "dataset": "PRIOR_CONVERSATION_RECAP_ONLY_NOT_VERIFIED_NOT_HOLDOUT",
            "n": n, "old_protection_hits": old_hit, "dynamic_protection_hits": new_hit,
            "old_protection_rate": old_hit/n, "dynamic_protection_rate": new_hit/n,
            "changed_pairs": changed, "ambiguous_second_slot_ties": tie_n,
            "training_or_threshold_fit": False, "independent_validation": False,
            "rows": detail}
