"""R6.3.6 2026-11-22: additive *research-only* prepublication exposure audit.

Never fit a parameter using results from Nov 21/22 known matches. Never modify
frozen Production, fulltime Q, ranked picks, protection pairs, or stake grades.
All calculations come from the SAME complete timestamped prematch score Q.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
import json
import math

from matchday_publish_gate_r636 import (
    GOALS, HTFT, WDL, EVIDENCE_FAMILIES, _dt, _score_grid,
    review, audit_aic_availability,
)

JC = ("让胜", "让平", "让负")
HIGH_TAIL = ("5", "6", "7+")
LOW_TAIL = ("0", "1")
PREMATCH_SIGNAL_FIELDS = frozenset({"family", "source_id", "observed_at", "tail"})


def _sha_canonical(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def _distinct_family_source_pairs(pairs):
    """Maximum matchable family/source pairs; one source cannot vote twice."""
    mapping = defaultdict(set)
    for family, source in pairs:
        mapping[family].add(source)
    owners = {}

    def match(family, visited):
        for source in sorted(mapping[family]):
            if source in visited:
                continue
            visited.add(source)
            if source not in owners or match(owners[source], visited):
                owners[source] = family
                return True
        return False

    return sum(match(f, set()) for f in sorted(mapping))


def _tail_evidence_review(signals, cutoff):
    """Signal families are audit inputs, NOT fitted probabilities or selections."""
    if not isinstance(signals, list):
        raise ValueError("tail signals must be a list of precutoff evidence")
    pairs = {"low": set(), "high": set()}
    seen = set()
    for s in signals:
        if not isinstance(s, dict) or set(s) != PREMATCH_SIGNAL_FIELDS:
            raise ValueError("exactly four prematch tail evidence fields required")
        if s["family"] not in EVIDENCE_FAMILIES or s["tail"] not in ("low", "high"):
            raise ValueError("unknown tail direction/family")
        if not isinstance(s["source_id"], str) or not s["source_id"].strip():
            raise ValueError("tail evidence source identifier required")
        if _dt(s["observed_at"]) > cutoff:
            raise ValueError("tail evidence postcutoff refused")
        pair = (s["tail"], s["family"], s["source_id"])
        if pair in seen:
            raise ValueError("duplicate tail evidence input")
        seen.add(pair)
        pairs[s["tail"]].add((s["family"], s["source_id"]))
    counts = {k: _distinct_family_source_pairs(pairs[k]) for k in ("low", "high")}
    ready = {k: counts[k] >= 2 for k in counts}
    contradictory = ready["low"] and ready["high"]
    if contradictory:
        status = "CONFLICTING_BIDIRECTIONAL_TAIL_SIGNALS_KEEP_ORIGINAL_Q"
    elif ready["low"]:
        status = "LOW_TAIL_EVIDENCE_MET_REVIEW_ONLY"
    elif ready["high"]:
        status = "HIGH_TAIL_EVIDENCE_MET_REVIEW_ONLY"
    else:
        status = "INSUFFICIENT_INDEPENDENT_PREMATCH_EVIDENCE"
    return {"matched_independent_families_and_sources": counts, "status": status,
            "low_evidence_gate": ready["low"] and not contradictory,
            "high_evidence_gate": ready["high"] and not contradictory,
            "original_goal_top3_must_remain_unchanged": True,
            "automatic_reweighting": False}


def _quality_proportions(probs):
    total = math.fsum(probs.values())
    if not math.isclose(total, 1.0, abs_tol=1e-8, rel_tol=0):
        raise AssertionError("original Q-derived probabilities not normalized")
    return total


def prematch_exposure_review(packet, *, tail_evidence=None, aic_records=None):
    """Wrapper around existing exact-prematch review, adding per-layer warnings.

    The packet cannot contain actual match outcomes; the inherited review rejects
    any unknown fields including postmatch score, cards, or substitutions.
    """
    before = _sha_canonical(packet)
    old = review(packet)
    cells = _score_grid(packet["score_grid"])
    c = _dt(packet["cutoff"])
    _quality_proportions(old["goal_buckets"])
    tail = _tail_evidence_review([] if tail_evidence is None else tail_evidence, c)
    aic = audit_aic_availability([] if aic_records is None else aic_records,
                                 cutoff=packet["cutoff"], kickoff=packet["kickoff"])
    jc = old["jc"]
    line = old["official_jc_line"]
    # All margin probabilities are derived from the original immutable Q.
    margin = old["exact_margin"]
    goal = old["goal_buckets"]
    scores = old["score_top3_derived"]
    score_cells = {(h, a): p for h, a, p in cells}
    score_top3_mass = math.fsum(score_cells[tuple(map(int, name.split(":")))] for name in scores)
    goal_top3_mass = math.fsum(goal[k] for k in old["goal_top3_derived"])
    jc_report = {"status": "BLOCK_OFFICIAL_SIGNED_JC_LINE_MISSING",
                 "letdraw_exact_margin": None, "letdraw_probability": None,
                 "letdraw_rank": None, "ranked_jc": None, "top1_vs_letdraw_gap": None,
                 "letdraw_score_top3_count": None, "one_goal_margin_home": margin.get(1, 0.0),
                 "one_goal_margin_away": margin.get(-1, 0.0),
                 "two_goal_margin_home": margin.get(2, 0.0),
                 "two_goal_margin_away": margin.get(-2, 0.0)}
    warnings = []
    if jc is not None:
        _quality_proportions(jc)
        ranked_jc = sorted(JC, key=lambda k: (-jc[k], JC.index(k)))
        exact = -line
        gap = jc[ranked_jc[0]] - jc["让平"]
        score_letdraw_count = sum(int(int(v.split(":")[0])-int(v.split(":")[1]) == exact) for v in scores)
        jc_report.update({"status": "RESEARCH_REVIEW_ONLY",
                          "letdraw_exact_margin": exact,
                          "letdraw_probability": jc["让平"],
                          "letdraw_rank": ranked_jc.index("让平")+1,
                          "ranked_jc": ranked_jc,
                          "top1_vs_letdraw_gap": gap,
                          "letdraw_score_top3_count": score_letdraw_count})
        if gap <= .05:  # 5 pp existing R6.3 review threshold, not fitted on Nov21
            warnings.append("LETDRAW_WITHIN_EXISTING_5PP_REVIEW_WINDOW_NO_AUTO_FLIP")
        if score_letdraw_count >= 2 and ranked_jc[0] != "让平":
            warnings.append("TWO_SCORE_TOP3_LETDRAW_FAMILY_BUT_AGGREGATE_JC_OTHER_REVIEW")
        if line in (-1, 1) and jc["让平"] > 0 and ranked_jc.index("让平") >= 1:
            warnings.append("PLUS_MINUS_ONE_JC_EXACT_MARGIN_UNDER_SELECTED_REVIEW_ONLY")
    nine = packet["htft_probabilities"]  # existing review already verifies FT marginals
    if nine is None:
        htft = {"status": "BLOCK_NO_VERIFIED_NINE_CLASS_PREMATCH_DISTRIBUTION",
                "nine_class_diagnostics": None, "top2_probability_mass": None,
                "full_nine_class_probabilities": None, "top2_existing_publication": list(packet["published_htft"])}
    else:
        ranked = sorted(HTFT, key=lambda k: (-nine[k], HTFT.index(k)))
        htft = {"status": "SHADOW_FT_MARGINALS_CONSISTENT",
                "full_nine_class_probabilities": dict(nine),
                "top2_existing_publication": list(packet["published_htft"]),
                "nine_class_diagnostics": {
                    "平平": nine["平平"], "负平": nine["负平"],
                    "胜平": nine["胜平"], "平负": nine["平负"],
                    "平胜": nine["平胜"], "负胜": nine["负胜"],
                    "胜负": nine["胜负"],
                    "from_half_time_trailing_to_draw_or_win": nine["负平"]+nine["负胜"],
                    "from_half_time_leading_to_draw_or_loss": nine["胜平"]+nine["胜负"],
                    "fulltime_draw_mass": math.fsum(nine[h+"平"] for h in WDL)},
                "top2_probability_mass": math.fsum(nine[k] for k in ranked[:2]),
                "top2_rank_gap": nine[ranked[1]]-nine[ranked[2]],
                "top3_from_frozen_nine": ranked[:3]}
        if nine[ranked[1]]-nine[ranked[2]] <= .03:
            warnings.append("HTFT_SECOND_THIRD_WITHIN_3PP_REVIEW_ONLY")
    if tail["status"].startswith("CONFLICT"):
        warnings.append("HIGH_LOW_TAIL_PREMATCH_EVIDENCE_CONFLICT_KEEP_CENTRAL_PEAK")
    if old["frozen_wdl"] != max(WDL, key=lambda k: old["wdl"][k]):
        warnings.append("FROZEN_WDL_Q_TOP1_CONFLICT_NO_AUTO_REVERSE")
    if old["wdl"]["平"] >= .20 and old["frozen_wdl"] != "平":
        warnings.append("DRAW_MASS_SIGNIFICANT_BUT_NOT_SELECTED_REVIEW_ONLY")
    if _sha_canonical(packet) != before:
        raise AssertionError("prematch packet was mutated by review")
    return {"version": "R636_NOV22_EXPOSURE_GUARDS_SHADOW", "research_only": True,
            "formal_grant": None, "production_weights_modified": False,
            "original_prematch_packet_sha256": before,
            "match_id": old["match_id"], "original_wdl_selection_unchanged": old["frozen_wdl"],
            "original_score_top3_unchanged": list(packet["published_score_top3"]),
            "original_goal_top3_unchanged": list(packet["published_goal_top3"]),
            "original_htft_top2_unchanged": list(packet["published_htft"]),
            "wdl_probabilities": dict(old["wdl"]),
            "original_component_release_gates": dict(old["component_release_gates"]),
            "score_top3_mass": score_top3_mass,
            "goal_top3_mass": goal_top3_mass,
            "goal_probs_0_6_7plus": dict(goal),
            "goal_families": {"zero": goal["0"], "one": goal["1"],
                              "central_2_3": goal["2"]+goal["3"], "edge_4": goal["4"],
                              "high_5_6_7plus": math.fsum(goal[k] for k in HIGH_TAIL)},
            "goal_tail_evidence": tail, "aic": aic,
            "jc_exact_margin": jc_report, "htft_state_distribution": htft,
            "warnings": warnings+old["warnings"],
            "automated_probability_update": None,
            "new_pick_or_core_grant": None}


def batch_exposure_review(preflight_records):
    """All exposure counts use original *prematch* probabilities; never results."""
    if not isinstance(preflight_records, list) or not preflight_records:
        raise ValueError("nonempty valid preflight records required")
    if any(not isinstance(x, dict) or x.get("version") != "R636_NOV22_EXPOSURE_GUARDS_SHADOW"
           for x in preflight_records):
        raise ValueError("only validated exposure records accepted")
    ids = [x["match_id"] for x in preflight_records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate match in batch")
    n = len(ids)
    selected = {z: sum(x["original_wdl_selection_unchanged"] == z for x in preflight_records) for z in WDL}
    expected = {z: math.fsum(x["wdl_probabilities"][z] for x in preflight_records) for z in WDL}
    jc_letdraw_expected = math.fsum(x["jc_exact_margin"]["letdraw_probability"] or 0. for x in preflight_records)
    jc_letdraw_top1 = sum(x["jc_exact_margin"]["ranked_jc"] is not None and
                           x["jc_exact_margin"]["ranked_jc"][0] == "让平" for x in preflight_records)
    goals = {k: {"expected_matches":math.fsum(x["goal_probs_0_6_7plus"][k] for x in preflight_records),
                 "matches_with_that_bucket_in_top3":sum(k in x["original_goal_top3_unchanged"] for x in preflight_records)}
             for k in GOALS}
    # Full prematch HTFT nine-way exposure, independent of postmatch outcomes.
    ht_expected = {k: 0.0 for k in HTFT}
    ht_top2_coverage = {k: 0 for k in HTFT}
    ht_evaluable = all(x["htft_state_distribution"].get("full_nine_class_probabilities") is not None
                       for x in preflight_records)
    if ht_evaluable:
        for x in preflight_records:
            nine = x["htft_state_distribution"]["full_nine_class_probabilities"]
            for k in HTFT:
                ht_expected[k] += nine[k]
                if k in x["htft_state_distribution"]["top2_existing_publication"]:
                    ht_top2_coverage[k] += 1
    draw_expected = expected["平"]
    flags = []
    if n >= 8 and selected["平"] == 0 and draw_expected >= 1.:
        flags.append("NO_DRAW_TOP1_DESPITE_EXPECTED_DRAW_MASS_REVIEW_ONLY")
    if n >= 8 and jc_letdraw_top1 == 0 and jc_letdraw_expected >= 1.:
        flags.append("NO_LETDRAW_TOP1_DESPITE_EXACT_MARGIN_MASS_REVIEW_ONLY")
    if n >= 8 and goals["0"]["matches_with_that_bucket_in_top3"] == 0 and goals["0"]["expected_matches"] >= 1.:
        flags.append("ZERO_GOAL_TOP3_COVERAGE_NONE_REVIEW_ONLY")
    if n >= 8 and sum(goals[k]["matches_with_that_bucket_in_top3"] for k in HIGH_TAIL) == 0 and sum(goals[k]["expected_matches"] for k in HIGH_TAIL) >= 1.:
        flags.append("ALL_HIGH_TAIL_TOP3_COVERAGE_NONE_REVIEW_ONLY")
    return {"version":"R636_NOV22_BATCH_PREMATCH_EXPOSURE_SHADOW", "n":n,
            "research_only":True,"formal_grant":None,
            "selected_wdl_count":selected,"sum_of_prematch_wdl_probabilities":expected,
            "expected_jc_letdraw_count":jc_letdraw_expected,
            "jc_letdraw_top1_selected_count":jc_letdraw_top1,
            "goal_bucket_exposure":goals,
            "htft_nine_class_expected_counts": ht_expected if ht_evaluable else None,
            "htft_class_top2_inclusion_counts": ht_top2_coverage if ht_evaluable else None,
            "htft_proper_probabilities_available_n": sum(
                x["htft_state_distribution"].get("full_nine_class_probabilities") is not None
                for x in preflight_records),
            "flags":flags,
            "original_predictions_unchanged":True}