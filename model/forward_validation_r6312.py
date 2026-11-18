"""R6.3.12 independent forward freeze/evaluate for joint-bridge research.

Postmatch score NEVER enters `shadow_r6312.inspect` or `joint.aggregate`.
Hashes detect modification, not trustworthy third-party timestamps.
"""
from __future__ import annotations
from collections import defaultdict
from math import log
from typing import Any
from datetime import datetime

import joint_bridge_r6312 as joint
import shadow_r6312
import forward_validation_r6311 as previous


def freeze(packet:dict,now:datetime|None=None)->dict:
    old=previous.freeze(packet,now=now)  # enforces real time < kickoff, source cutoff
    new=shadow_r6312.inspect(packet)
    bridge=new["S4_GS_RC_unified_probability_bridge_v312"]
    watch=new["S4_GS_RC_cross_layer_hardlock_v312"]
    rec={"schema":"M79_R6312_FORWARD_FREEZE_V1",
         "old_r6311_snapshot":old,
         "joint_bridge_result":bridge,
         "cross_layer_warning_state":watch,
         "match_id":old["match_id"],
         "cutoff":old["cutoff"],"kickoff":old["kickoff"],
         "created_at_utc":old["created_at_utc"],
         "input_packet_sha256":old["input_packet_sha256"],
         "candidate_not_formal_grant":True,
         "production_unchanged":True}
    rec["snapshot_sha256"]=previous.digest(rec)
    return rec


def _check(s:dict)->None:
    if not isinstance(s,dict) or s.get("schema")!="M79_R6312_FORWARD_FREEZE_V1":
        raise ValueError("invalid R6312 frozen snapshot schema")
    rest={k:v for k,v in s.items() if k!="snapshot_sha256"}
    if s.get("snapshot_sha256")!=previous.digest(rest):
        raise ValueError("R6312 snapshot hash mismatch")
    previous._check_snapshot(s["old_r6311_snapshot"])
    if s["match_id"]!=s["old_r6311_snapshot"]["match_id"]:
        raise ValueError("nested snapshot match id changed")
    if s["input_packet_sha256"]!=s["old_r6311_snapshot"]["input_packet_sha256"]:
        raise ValueError("nested input digest mismatch")


def _brier_likelihood(probabilities:dict[str,float],actual:str)->dict:
    return {"brier":sum((p-float(k==actual))**2 for k,p in probabilities.items()),
            "log_loss":-log(probabilities[actual]) if probabilities[actual]>0 else None,
            "zero_mass_event":probabilities[actual]==0}


def evaluate(snapshot:dict,actual:dict)->dict:
    _check(snapshot)
    previous_row=previous.evaluate(snapshot["old_r6311_snapshot"],actual)
    score=actual["score"]
    h,a=joint.parse_score(score)
    bridge=snapshot["joint_bridge_result"]
    wdl=joint.wdl_label(h,a)
    goal=joint.goal_bucket(h,a)
    eligible=bridge.get("status")=="ONE_JOINT_GRID_VALIDATED"
    jc=None; jc_hit=None; jc_brier=None
    wdl_brier=None; goal_brier=None
    if eligible:
        wdl_brier=_brier_likelihood(bridge["wdl_probabilities"],wdl)
        goal_brier=_brier_likelihood(bridge["goal_bucket_probabilities"],goal)
        line=bridge["official_signed_jc_line"]
        if line is not None:
            jc=joint.jc_label(h,a,line)
            jc_hit=bridge["jc_integrated_rank"][0]==jc
            jc_brier=_brier_likelihood(bridge["jc_probabilities"],jc)
    raw_score_hit=(score in bridge["raw_score_top3"]) if eligible else None
    raw_goal_hit=(goal in bridge["raw_goal_bucket_top3"]) if eligible else None
    goal_anchor_hits={c["missing_goal_bucket"]:score in c["score_top3_candidate"]
                      for c in bridge.get("goal_anchor_challengers",[])} if eligible else {}
    return {"match_id":snapshot["match_id"],"snapshot_sha256":snapshot["snapshot_sha256"],
            "actual_score":score,"observed_at":actual["observed_at"],
            "baseline_r6311":previous_row,
            "joint_bridge_eligible":eligible,
            "bridge_wdl_log_brier":wdl_brier,"bridge_goal_log_brier":goal_brier,
            "bridge_jc_log_brier":jc_brier,
            "raw_grid_score_top3_hit":raw_score_hit,
            "raw_grid_goal_top3_hit":raw_goal_hit,
            "bridge_jc_research_top1_hit":jc_hit,
            "bridge_jc_actual":jc,
            "goal_anchor_challenger_score_hits":goal_anchor_hits,
            "no_backward_fit_from_actual_score":True,
            "no_formal_accuracy_certification":True}


def summary(scored:list[dict])->dict:
    if not isinstance(scored,list):raise ValueError("rows must be a list")
    ids=[r["match_id"] for r in scored]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate match ids")
    # Eligibility-specific denominators prevent missing JC lines from being scored as misses.
    stats={}
    for field in ("raw_grid_score_top3_hit","raw_grid_goal_top3_hit","bridge_jc_research_top1_hit"):
        vals=[r[field] for r in scored if r.get(field) is not None]
        stats[field]={"hits":sum(vals),"n":len(vals)}
    losses={}
    for key in ("bridge_wdl_log_brier","bridge_goal_log_brier","bridge_jc_log_brier"):
        vals=[r[key] for r in scored if r.get(key) is not None]
        losses[key]={"n":len(vals),
                     "mean_brier":sum(v["brier"] for v in vals)/len(vals) if vals else None,
                     "mean_log_loss":(sum(v["log_loss"] for v in vals)/len(vals)
                                      if vals and all(v["log_loss"] is not None for v in vals) else None),
                     "unmodelled_actual_event_count":sum(v["zero_mass_event"] for v in vals)}
    return {"matches":len(scored),"eligible_bridge_matches":sum(r["joint_bridge_eligible"] for r in scored),
            "hits":stats,"probability_scores":losses,
            "minimum_50_required_for_promotion_review":len(scored)>=50,
            "preferred_100_for_stability":len(scored)>=100,
            "independent_validation_only_not_20261116_development":True,
            "production_grant":None}
