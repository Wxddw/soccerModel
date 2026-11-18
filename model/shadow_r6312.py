"""R6.3.12 read-only, mass-preserving joint bridge and selection warning gates.

M79.3.6 remains frozen. This is not a trained model and cannot grant bets.
No postmatch input, alternative weights, or automatic score/goal/JC switch.
"""
from __future__ import annotations

import math
import shadow_r6311 as prev
import joint_bridge_r6312 as joint

VERSION="M79.3.6_SHADOW_R6.3.12_20261117"
WDL=joint.WDL
GOAL=joint.GOALS
JC=joint.JC
FROZEN_GAP_WATCH=0.05  # inherited S4 review width; not a fitted threshold
TOP1_UNDER_40=.40       # inherited selection discipline
STRICT_GRID_ALIGNMENT=1e-6
POSTMATCH_FIELDS={"actual_score","actual_result","final_score","full_time_score",
                  "actual_final_score","match_outcome","result_timestamp",
                  "score_result","recap_20261116","postmatch_20261116",
                  "match_events","in_play_events","actual_handicap"}


def _watch(packet:dict, parent:dict, bridge:dict) ->dict:
    """Compare named frozen/routed choices to the one grid; no authority changes."""
    flags=[]; blocking=[]; review=[]
    derived=bridge["wdl_probabilities"]
    inherited=parent["outcome_probabilities_unchanged"]
    wdl_delta={k:derived[k]-float(inherited[i]) for i,k in enumerate(WDL)}
    if max(abs(v) for v in wdl_delta.values())>STRICT_GRID_ALIGNMENT:
        blocking.append("FROZEN_WDL_NOT_EXACTLY_DERIVED_FROM_SAME_GRID")
    goal_delta=None
    if packet.get("goal_distribution") is not None:
        goal_delta={k:bridge["goal_bucket_probabilities"][k]-float(packet["goal_distribution"][k]) for k in GOAL}
        if max(abs(v) for v in goal_delta.values())>STRICT_GRID_ALIGNMENT:
            blocking.append("FROZEN_RC_GOAL_BUCKETS_NOT_EXACTLY_DERIVED_FROM_SAME_GRID")
    contract=parent.get("S4_v1_7_official_handicap_contract",{})
    signed_line=bridge["official_signed_jc_line"]
    jc_delta=None
    if signed_line is not None:
        hp=contract.get("handicap_probabilities")
        if isinstance(hp,dict):
            jc_delta={k:bridge["jc_probabilities"][k]-float(hp[k]) for k in JC}
            if max(abs(v) for v in jc_delta.values())>STRICT_GRID_ALIGNMENT:
                blocking.append("FROZEN_JC_OUTCOME_NOT_EXACTLY_DERIVED_FROM_SAME_GRID")
    else:
        blocking.append("NO_TIMESTAMPED_OFFICIAL_JC_INTEGER_LINE_NO_HANDICAP_GRANT")
    jc_rank=bridge["jc_integrated_rank"]
    frozen_pick=contract.get("frozen_handicap_pick") if signed_line is not None else None
    first=second=gap=let_draw_gap=None
    if jc_rank is not None:
        first,second=jc_rank[:2]
        probs=bridge["jc_probabilities"]
        gap=probs[first]-probs[second]
        let_draw_gap=probs[first]-probs["让平"]
        if gap<=FROZEN_GAP_WATCH+1e-12:
            review.append("JC_TOP_TWO_WITHIN_5PP_PROTECT_REVIEW")
        if first!="让平" and let_draw_gap<=FROZEN_GAP_WATCH+1e-12:
            review.append("LET_DRAW_NEAR_BEST_JC_MARGIN_REVIEW")
        if probs[first] < TOP1_UNDER_40:
            review.append("JC_BEST_BELOW_40PCT_RESEARCH_ONLY")
        if first!=frozen_pick:
            review.append("FROZEN_JC_PICK_CONFLICTS_WITH_GRID_AGGREGATE")
        draw_scores=[s for s in bridge["score_top3_cross_layer_mapping"] if s["jc"]=="让平"]
        if len(draw_scores)>=2 and frozen_pick!="让平":
            review.append("MULTIPLE_TOP3_SCORES_POINT_TO_JC_LET_DRAW")
        # The modal exact score may disagree with aggregate JC. This is NOT an
        # arithmetic contradiction, but it should be explained on output.
        if bridge["score_top3_cross_layer_mapping"][0]["jc"]!=first:
            review.append("MOST_LIKELY_EXACT_SCORE_MAPS_TO_DIFFERENT_JC_OUTCOME")
    router=parent.get("RC2_5_exact_bucket_router",{})
    routed=router.get("shadow_top3")
    if isinstance(routed,list) and routed!=bridge["raw_goal_bucket_top3"]:
        flags.append("TAIL_ROUTED_GOAL_TOP3_DIFFERS_FROM_RAW_GRID_TOP3_NOT_ARITHMETIC_ERROR")
    if bridge["goal_anchor_challengers"]:
        flags.append("GOAL_TOP3_BUCKETS_ABSENT_FROM_GLOBAL_SCORE_TOP3_RESEARCH_CHALLENGER_ONLY")
    if (signed_line is not None and
            bridge["score_top3_cross_layer_mapping"][0]["wdl"]!=max(WDL,key=lambda k:derived[k])):
        flags.append("SCORE_TOP1_WDL_DIFFERS_FROM_AGGREGATE_WDL_NOT_ARITHMETIC_ERROR")
    # Always suppress formal grants: these states are for human review only.
    status=("BLOCK_BAD_CROSS_LAYER_DATA" if blocking else
            "HANDICAP_MANUAL_REVIEW" if review else "LINKED_READ_ONLY_CLEAR")
    advice=("封锁：数据不一致或无官方让球盘口" if blocking else
            "暂停让球单挑；复核让平与邻近净胜差" if review else
            "可观察矩阵研究首选；不授予正式单挑")
    return {"version":"S4_GS_RC_Lock_v1", "status":status,
            "wdl_vs_joint_delta":wdl_delta,"goals_vs_joint_delta":goal_delta,
            "jc_vs_joint_delta":jc_delta,
            "blocking_reasons":blocking,"manual_review_reasons":review,
            "diagnostic_not_mathematical_errors":flags,
            "research_jc_first":first,"research_jc_protection_candidate":jc_rank[:2] if jc_rank else None,
            "official_frozen_jc_pick_unchanged":frozen_pick,
            "research_jc_first_gap":gap,"let_draw_gap":let_draw_gap,
            "let_draw_signed_margin":bridge["let_draw_margin"],
            "let_draw_exact_probability":bridge["exact_let_draw_probability"],
            "risk_message_cn":advice,
            "handicap_single_eligible_for_automatic_grant":False,
            "goal_score_link_verified":not any("FROZEN_WDL" in x or "FROZEN_RC" in x for x in blocking),
            "complete_handicap_link_verified":not blocking,
            "probability_adjustment":False,"direction_flip":False,"formal_handicap_grant":None}


def inspect(packet:dict)->dict:
    if not isinstance(packet,dict):raise ValueError("prematch packet must be dict")
    if any(k in POSTMATCH_FIELDS or k.startswith(('actual_', 'postmatch_', 'recap_'))
           for k in packet):
        raise ValueError("prematch packet contains forbidden replay-only field")
    parent=prev.inspect(packet)
    raw=packet.get("score_matrix")
    if not raw or parent.get("GS1_3_joint_score_audit",{}).get("status")!="JOINT_MATRIX_COHERENT":
        bridge={"version":"S4_GS_RC_OneJointGrid_R6.3.12",
                "status":"UNKNOWN_NO_COHERENT_PREMATCH_JOINT_GRID",
                "wdl_probabilities":None,"goal_bucket_probabilities":None,
                "jc_probabilities":None,"raw_goal_bucket_top3":None,"raw_score_top3":None,
                "formal_handicap_grant":None,"probability_adjustment":False}
        audit={"version":"S4_GS_RC_Lock_v1", "status":"BLOCK_NO_JOINT_GRID",
               "risk_message_cn":"规避：无法证明比分、总球与让球来自同一矩阵",
               "handicap_single_eligible_for_automatic_grant":False,
               "formal_handicap_grant":None,"probability_adjustment":False}
    else:
        contract=parent.get("S4_v1_7_official_handicap_contract",{})
        line=contract.get("official_handicap_line")
        bridge=joint.aggregate(raw,line)
        audit=_watch(packet,parent,bridge)
    flags=list(parent.get("audit_flags_r6311",[]))
    flags.extend(audit.get("blocking_reasons",[]))
    flags.extend(audit.get("manual_review_reasons",[]))
    flags.extend(audit.get("diagnostic_not_mathematical_errors",[]))
    if bridge["status"].startswith("UNKNOWN"):
        flags.append("R6312_MISSING_JOINT_GRID_HOLD")
    return {**parent,
            "version":VERSION,
            "S4_GS_RC_unified_probability_bridge_v312":bridge,
            "S4_GS_RC_cross_layer_hardlock_v312":audit,
            "audit_flags_r6312":list(dict.fromkeys(flags)),
            "probability_adjustment_applied":False,
            "outcome_probabilities_unchanged":parent["outcome_probabilities_unchanged"],
            "formal_single_grant":None,"formal_core_grant":None,
            "formal_protection_grant":None,"formal_handicap_grant":None,
            "automatic_direction_flip":False,"production_changed":False,
            "postmatch_training_performed":False,
            "notes_r6312":["All WDL, JC, integer goals and scores are reaggregated from one frozen joint matrix.",
              "The original outcome/goal/handicap selections are not altered; mismatches HOLD the release.",
              "A modal exact score and aggregate JC outcome can differ without mathematical inconsistency.",
              "An omitted goal bucket in score Top3 adds a goal-anchored challenger, never a forced pick.",
              "No production weights or calibration parameters refitted; independent forward evidence required."]}
