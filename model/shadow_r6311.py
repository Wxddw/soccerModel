"""R6.3.11 forward-research overlay: evidence hygiene + score-challenger candidates.

NO past outcomes or replay labels are used in prematch execution.  The old
Production and R6.3.10 channels remain unchanged.  Challenger candidates are
for future paired evaluation, not grants or claims of improved calibration.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any
import copy
import math

import selection_efficiency_r633 as base
import shadow_r637 as r637
import shadow_r639 as r639
import shadow_r6310 as prev

VERSION = "M79.3.6_SHADOW_R6.3.11_20261115"
FAMILIES = {"form", "squad", "replacement", "tactics", "motivation", "schedule", "matchup", "xg"}
SQUAD_GROUP = {"squad", "replacement"}
ALLOWED_SIGNAL = {"home", "away", "neutral", "uncertain"}
ALLOWED_CERTAINTY = {"confirmed", "reported", "projected", "unknown"}
ALLOWED_PROVENANCE = {"football_only", "market_only", "hybrid", "unknown"}


def _football_evidence_v0311(packet: dict) -> dict:
    """Source/timestamp/dedup checks; never converts labels into numeric weights."""
    raw = packet.get("football_evidence_v311")
    if raw is None:
        return {"version":"ESR_Form_v0.3", "status":"UNKNOWN_NO_FOOTBALL_ONLY_EVIDENCE",
                "independent_groups":[], "flags":["FOOTBALL_CHANNEL_UNVERIFIED"],
                "core_manual_review":True, "probability_adjustment":False,
                "auto_direction_flip":False, "new_risk_family_votes":0}
    if not isinstance(raw,list):
        raise ValueError("football_evidence_v311 must be list")
    cutoff = base._time(packet["cutoff"],"cutoff")
    seen = {}
    detail=[]; flags=[]; family_groups=set()
    for i, row in enumerate(raw):
        if not isinstance(row,dict):
            raise ValueError("football evidence item must be source-backed object")
        allowed={"family","side","signal","certainty","event_id","source_id","observed_at", "opponent_adjusted", "replacement_quality"}
        if set(row)-allowed:
            raise ValueError("unrecognized football_evidence_v311 fields")
        family=row.get("family"); side=row.get("side")
        if family not in FAMILIES or side not in ("home","away","both"):
            raise ValueError("invalid football evidence family/side")
        if row.get("signal") not in ALLOWED_SIGNAL or row.get("certainty") not in ALLOWED_CERTAINTY:
            raise ValueError("invalid football signal/certainty")
        event_id=row.get("event_id")
        if not isinstance(event_id,str) or not event_id.strip():
            raise ValueError("football evidence requires stable nonblank event_id")
        source_id,stamp=r637._time_record(row,f"football_evidence_v311[{i}]",cutoff)
        if "opponent_adjusted" in row and family!="form":
            raise ValueError("opponent_adjusted only applies to form")
        if "replacement_quality" in row and family not in SQUAD_GROUP:
            raise ValueError("replacement_quality only applies to squad/replacement")
        if "opponent_adjusted" in row and type(row["opponent_adjusted"]) is not bool:
            raise ValueError("opponent_adjusted must be bool")
        if row.get("replacement_quality") not in (None,"verified_equal","verified_better","verified_worse","unknown"):
            raise ValueError("replacement_quality invalid")
        group = "roster" if family in SQUAD_GROUP else family
        duplicate=event_id in seen
        if duplicate:
            if seen[event_id] != (side, row["signal"]):
                raise ValueError("same event_id cannot give contradictory side/signal")
            flags.append("DUPLICATE_CAUSAL_EVENT_NOT_DOUBLE_COUNTED")
        else:
            seen[event_id]=(side,row["signal"])
            family_groups.add(group)
        if family=="form" and row.get("opponent_adjusted") is not True:
            flags.append("UNADJUSTED_FORM_NEEDS_OPPONENT_QUALITY_REVIEW")
        if family in SQUAD_GROUP and row.get("replacement_quality") in (None,"unknown"):
            flags.append("UNVERIFIED_REPLACEMENT_QUALITY_NO_STRENGTH_INFERENCE")
        if row["certainty"] in ("projected","unknown"):
            flags.append("UNCONFIRMED_FOOTBALL_SIGNAL_NOT_A_FACT")
        detail.append({"event_id":event_id,"family":family,"evidence_group":group,
                       "side":side,"signal":row["signal"],"certainty":row["certainty"],
                       "source_id":source_id,"observed_at":stamp,
                       "opponent_adjusted":row.get("opponent_adjusted"),
                       "replacement_quality":row.get("replacement_quality"),
                       "deduplicated":duplicate})
    if not raw: flags.append("EMPTY_EVIDENCE_IS_UNKNOWN_NOT_CLEAR")
    flags=list(dict.fromkeys(flags))
    return {"version":"ESR_Form_v0.3",
            "status":"EVIDENCE_QUALITY_REVIEW" if flags else "SOURCE_TIME_DEDUP_AUDITED",
            "events":detail,"unique_causal_events":len(seen),
            "independent_groups":sorted(family_groups),
            "roster_and_replacement_are_one_group":True,
            "core_manual_review":bool(flags),"flags":flags,
            "probability_adjustment":False,"auto_direction_flip":False,
            "new_risk_family_votes":0}


def _channel_provenance(packet:dict) ->dict:
    value=packet.get("matrix_provenance_v311")
    if value is None:
        return {"status":"UNKNOWN_MATRIX_SOURCE", "declared_channel":None,
                "football_only_claim_verified":False}
    if not isinstance(value,dict) or set(value)!={"source_id","observed_at","channel","model_id"}:
        raise ValueError("matrix_provenance_v311 requires source_id, observed_at, channel, model_id")
    cutoff=base._time(packet["cutoff"],"cutoff")
    source,stamp=r637._time_record(value,"matrix_provenance_v311",cutoff)
    channel=value["channel"]
    if channel not in ALLOWED_PROVENANCE:
        raise ValueError("invalid matrix_provenance_v311 channel")
    if not isinstance(value["model_id"],str) or not value["model_id"].strip():
        raise ValueError("model_id required")
    # Forbid explicitly claiming football-only while supplying market-family evidence.
    if channel=="football_only" and any(r.get("family")=="market_price" for r in packet.get("evidence",[])):
        raise ValueError("football_only matrix conflicts with market_price evidence")
    return {"status":"SOURCE_DECLARED_NOT_INDEPENDENTLY_CERTIFIED",
            "declared_channel":channel,"source_id":source,"observed_at":stamp,
            "model_id":value["model_id"],"football_only_claim_verified":False}


def _score_top3_challengers(packet:dict, parent:dict)->dict:
    """Prospective alternate Top3 based solely on a frozen coherent Q matrix.

    Raw global Top3 maximizes model-estimated Top3 probability. Diversity can
    only lower or tie its probability mass under that same matrix; it is a
    diagnostic challenger requiring independent forward evidence.
    """
    matrix=prev._valid_joint(packet,parent)
    if matrix is None:
        return {"version":"GS1.8", "status":"UNKNOWN_NO_COHERENT_JOINT",
                "raw_global_top3":None,"challengers":None,
                "probability_adjustment":False,"formal_score_grant":None}
    rows=sorted(matrix,key=lambda r:(-float(r["probability"]),r["score"]))
    top3=rows[:3]
    mass=lambda ar:sum(float(r["probability"]) for r in ar)
    family=lambda r:("胜" if r639._score(r["score"])[0]>r639._score(r["score"])[1] else
                     "平" if r639._score(r["score"])[0]==r639._score(r["score"])[1] else "负")
    btts=lambda r:all(v>0 for v in r639._score(r["score"]))
    jc=parent.get("S4_v2_0_signed_margin_boundary_audit",{})
    line=jc.get("official_jc_integer_line")
    def handicap(r):
        h,a=r639._score(r["score"]); m=h-a+line
        return "让胜" if m>0 else "让平" if m==0 else "让负"
    def to_result(arr,name):
        arr=sorted(arr,key=lambda r:(-float(r["probability"]),r["score"]))
        am=mass(arr)
        return {"name":name,"score_top3":[r["score"] for r in arr],
                "selected_joint_mass":round(am,9),
                "loss_vs_global_top3":round(max(0,mass(top3)-am),9),
                "wdl_families":sorted({family(r) for r in arr}),
                "btts_states":sorted({str(btts(r)) for r in arr}),
                "score_top3_changed": {r["score"] for r in arr}!={r["score"] for r in top3}}
    outs=[]
    # At least two WDL outcome families when possible; no forced draw direction.
    div=list(top3)
    if len({family(r) for r in div})==1:
        alt=next((r for r in rows[3:] if family(r)!=family(top3[0])),None)
        if alt is not None:div=[top3[0],top3[1],alt]
    outs.append(to_result(div,"wdl_family_diversity_candidate"))
    # Both-teams-score hedge if original raw top3 had only BTTS or only NOT BTTS.
    hedge=list(top3)
    if len({btts(r) for r in hedge})==1:
        alt=next((r for r in rows[3:] if btts(r)!=btts(top3[0])),None)
        if alt is not None:hedge=[top3[0],top3[1],alt]
    outs.append(to_result(hedge,"btts_diversity_candidate"))
    if line is not None:
        margin=list(top3)
        if len({handicap(r) for r in margin})==1:
            alt=next((r for r in rows[3:] if handicap(r)!=handicap(top3[0])),None)
            if alt is not None:margin=[top3[0],top3[1],alt]
        outs.append(to_result(margin,"jc_margin_family_diversity_candidate"))
    def total(r):return sum(r639._score(r["score"]))
    top_tail={}
    for key,predicate in (("zero_goals",lambda n:n==0),("five_six_goals",lambda n:5<=n<=6),
                          ("seven_plus_goals",lambda n:n>=7)):
        item=next((r for r in rows if predicate(total(r))),None)
        top_tail[key] = None if item is None else {"score":item["score"],
             "joint_mass":round(float(item["probability"]),9),"is_in_original_top3":item in top3}
    return {"version":"GS1.8","status":"PARETO_ALTERNATIVES_READ_ONLY",
            "raw_global_top3":to_result(top3,"raw_mass_optimal_top3"),
            "challengers":outs,"tail_score_watch":top_tail,
            "raw_global_top3_is_optimal_for_matrix":True,
            "alternatives_need_independent_forward_test":True,
            "score_top3_automatic_replacement":False,
            "probability_adjustment":False,"formal_score_grant":None}


def _decision_risk_v311(packet:dict, parent:dict, evidence:dict, provenance:dict)->dict:
    flags=list(evidence.get("flags",[]))
    objective=parent.get("Selection_Context_v0_8",{})
    if objective.get("core_manual_review"):
        flags.append("INHERITED_OBJECTIVE_OR_FRIENDLY_CORE_REVIEW")
    side=parent.get("Selection_Efficiency_v0_8",{})
    core=side.get("core_candidate_review")
    # No subjective risk vote or selection flip is generated here.
    return {"version":"Selection_Context_v0.9", "status":"REVIEW_ONLY" if flags else "NO_NEW_FLAGS",
            "source_channel_status":provenance.get("status"),
            "football_context_flags":list(dict.fromkeys(flags)),
            "old_core_candidate_review_unchanged":core,
            "core_review_only":bool(flags),"new_independent_risk_family_votes":0,
            "formal_core_grant":None, "formal_direction_grant":None,
            "auto_direction_flip":False,"probability_adjustment":False}


def inspect(packet:dict)->dict:
    if not isinstance(packet,dict):raise ValueError("prematch packet must be object")
    # Deny replay data explicitly even if absent from inherited prohibitions.
    forbidden=prev.REPLAY_ONLY_FIELDS|{"final_score", "full_time_score", "match_outcome",
                                     "result_timestamp", "actual_final_score", "score_result"}
    if forbidden.intersection(packet):
        raise ValueError("R6.3.11 prematch packet contains forbidden postmatch fields")
    inherited=prev.inspect(packet)
    football=_football_evidence_v0311(packet)
    prov=_channel_provenance(packet)
    scores=_score_top3_challengers(packet,inherited)
    risk=_decision_risk_v311(packet,inherited,football,prov)
    flags=list(inherited.get("audit_flags_r6310",[]))
    flags.extend(football.get("flags",[]))
    flags.extend(risk.get("football_context_flags",[]))
    return {**inherited,"version":VERSION,
            "ESR_Form_v0_3_evidence_quality":football,
            "score_matrix_provenance_audit_v311":prov,
            "GS1_8_forward_score_challengers":scores,
            "Selection_Context_v0_9_forward_hygiene":risk,
            "audit_flags_r6311":list(dict.fromkeys(flags)),
            "outcome_probabilities_unchanged":inherited["outcome_probabilities_unchanged"],
            "probability_adjustment_applied":False, "automatic_direction_flip":False,
            "formal_single_grant":None,"formal_core_grant":None,
            "formal_protection_grant":None,"formal_handicap_grant":None,
            "production_changed":False,"postmatch_training_performed":False,
            "notes_r6311":["Nov14 14-match recap is development-only, never prematch training or holdout.",
               "Football evidence requires precutoff sources; recent form without opponent adjustment triggers review.",
               "Raw matrix Top3 maximizes its own probability mass; diversity challengers can only match or reduce it.",
               "Forward comparison of candidate score coverage is prospective, not an accuracy claim.",
               "All inherited production and selection grants remain frozen/unauthorized."]}
