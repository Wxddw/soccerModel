"""M79.3.6 Shadow R6.3.7: symmetric direction-risk, ESR functionality,
selection/core evidence separation, score-family runners-up, and official
Chinese-football-lottery handicap contract.

Research-only overlay on R6.3.6. It never changes WDL probabilities, flips a
unique direction, or issues a formal single/core/protection/handicap grant.
All evidence must be source-backed and timestamped before the frozen cutoff.
"""
from __future__ import annotations
from typing import Any
import shadow_r636 as r636
import selection_efficiency_r633 as base

VERSION = "M79.3.6_SHADOW_R6.3.7_20261109"
WDL = ("胜", "平", "负")
FAMILY_GROUP = {
    "roster": "roster", "injury": "roster", "official_lineup": "roster",
    "goalkeeper": "roster", "defensive_spine": "roster", "bench_quality": "roster",
    "schedule": "schedule", "rotation": "schedule", "short_turnaround": "schedule",
    "tactical": "tactical", "tactical_matchup": "tactical", "opponent_transition": "tactical",
    "set_piece_matchup": "tactical", "coach_transition": "tactical",
    "opponent_strength": "opponent_strength", "home_strength": "opponent_strength",
    "form_strength": "opponent_strength",
    "market": "market", "market_price": "market", "market_flow": "market", "kelly": "market",
}
FAVORITE_FAMILIES = {"roster", "schedule", "tactical", "opponent_strength", "market"}


def _time_record(rec: Any, label: str, cutoff) -> tuple[str, str]:
    if not isinstance(rec, dict): raise ValueError(f"{label} must be a source record")
    sid = rec.get("source_id")
    if not isinstance(sid, str) or not sid.strip(): raise ValueError(f"{label}.source_id required")
    dt = base._time(rec.get("observed_at"), f"{label}.observed_at")
    if dt > cutoff: raise ValueError(f"{label} is post-cutoff")
    return sid, dt.isoformat()


def _role_functionality(parent: dict, raw_direction: str) -> dict:
    """Expose GK, defensive-spine and attacking-unit changes; all one roster family."""
    squad = parent.get("effective_squad_ESR", {})
    if squad.get("status") not in ("CONFIRMED_BOTH", "PROJECTED_AT_LEAST_ONE"):
        return {"version":"ESR_Functionality_v0.1", "status":"UNKNOWN_NO_COMPLETE_ESR",
                "raw_direction":raw_direction, "role_shift_home_minus_away":None,
                "direction_adjusted_role_shift":None, "flags":[],
                "independent_families_added":0, "probability_adjustment":False}
    sides=squad.get("sides", {})
    if not all(k in sides for k in ("home","away")):
        return {"version":"ESR_Functionality_v0.1", "status":"UNKNOWN_ESR_ROLE_DATA_INCOMPLETE",
                "raw_direction":raw_direction, "role_shift_home_minus_away":None,
                "direction_adjusted_role_shift":None, "flags":[],
                "independent_families_added":0, "probability_adjustment":False}
    h=sides["home"].get("role_contributions", {}); a=sides["away"].get("role_contributions", {})
    groups={
      "goalkeeper":float(h.get("goalkeeper",0.0))-float(a.get("goalkeeper",0.0)),
      "defensive_spine":float(h.get("center_back",0.0))+float(h.get("defensive_midfielder",0.0))-float(a.get("center_back",0.0))-float(a.get("defensive_midfielder",0.0)),
      "attacking_unit":float(h.get("attacking_midfielder",0.0))+float(h.get("winger",0.0))+float(h.get("striker",0.0))-float(a.get("attacking_midfielder",0.0))-float(a.get("winger",0.0))-float(a.get("striker",0.0)),
    }
    sign=1.0 if raw_direction=="胜" else -1.0
    adjusted={k:sign*v for k,v in groups.items()}
    flags=[]
    if adjusted["goalkeeper"]<=-.75: flags.append("RAW_DIRECTION_GOALKEEPER_REPLACEMENT_QUALITY_DROP")
    if adjusted["defensive_spine"]<=-1.50: flags.append("RAW_DIRECTION_DEFENSIVE_SPINE_QUALITY_DROP")
    if adjusted["attacking_unit"]<=-1.50: flags.append("RAW_DIRECTION_ATTACKING_UNIT_QUALITY_DROP")
    eff=squad.get("effective_quality_home_minus_away"); shift=squad.get("relative_shift")
    effdir=None if eff is None else sign*float(eff); shiftdir=None if shift is None else sign*float(shift)
    if effdir is not None and shiftdir is not None:
        if effdir<=-2 and shiftdir<=-2: alignment="DUAL_ADVERSE_TO_RAW_DIRECTION"
        elif effdir>=2 and shiftdir>=2: alignment="DUAL_SUPPORTS_RAW_DIRECTION"
        elif effdir<=-2 or shiftdir<=-2 or flags: alignment="ADVERSE_COMPONENT_REVIEW"
        else: alignment="MIXED_OR_NEAR_NEUTRAL"
    else: alignment="UNKNOWN_ESR_DIRECTIONAL_GAP"
    return {"version":"ESR_Functionality_v0.1", "status":squad.get("status"),
            "raw_direction":raw_direction,
            "role_shift_home_minus_away":{k:round(v,4) for k,v in groups.items()},
            "direction_adjusted_role_shift":{k:round(v,4) for k,v in adjusted.items()},
            "effective_quality_gap_aligned_to_direction":None if effdir is None else round(effdir,4),
            "lineup_relative_shift_aligned_to_direction":None if shiftdir is None else round(shiftdir,4),
            "alignment":alignment,"flags":flags,"roster_is_one_independent_family":True,
            "probability_adjustment":False}


def _direction_vulnerability_gate(packet: dict, parent: dict, raw_direction: str,
                                  probabilities: list[float], functionality: dict) -> dict:
    """Symmetric vulnerability review for home/away Top1; risk evidence is deduped by cause."""
    rank=r636._rank_wdl(probabilities); top1=probabilities[rank[0]]
    if raw_direction=="平" or top1<.40:
        return {"version":"DVRG_v0.1","status":"NOT_APPLICABLE_DRAW_OR_WEAK_DIRECTION",
                "raw_direction":raw_direction,"direction_side":None,"independent_families":{},
                "family_count":0,"adverse_family_count":0,"critical_roster_risk":False,
                "authorization_effect":"NO_DIRECTIONAL_CORE_REVIEW","probability_adjustment":False,
                "automatic_direction_flip":False}
    side="home" if raw_direction=="胜" else "away"
    cutoff=base._time(packet["cutoff"],"cutoff")
    direct=packet.get("favorite_risk_evidence"); legacy=packet.get("risk_evidence")
    if direct is not None and legacy is not None:
        raise ValueError("use favorite_risk_evidence OR legacy home-relative risk_evidence, not both")
    families={}; critical=False
    if direct is not None:
        if not isinstance(direct,list): raise ValueError("favorite_risk_evidence must be a list")
        for rec in direct:
            if not isinstance(rec,dict): raise ValueError("favorite_risk_evidence item must be an object")
            fam=rec.get("family")
            if fam not in FAVORITE_FAMILIES: raise ValueError("unsupported favorite-risk family")
            if fam in families: raise ValueError(f"correlated favorite-risk family duplicated: {fam}")
            sid,stamp=_time_record(rec,f"favorite_risk_evidence.{fam}",cutoff)
            state=rec.get("state")
            if state not in ("adverse_to_favorite","neutral","favorable_to_favorite"):
                raise ValueError("favorite-risk state must be adverse_to_favorite/neutral/favorable_to_favorite")
            severe=rec.get("critical_spine_severe",False)
            if type(severe) is not bool: raise ValueError("critical_spine_severe must be boolean")
            if severe and (fam!="roster" or state!="adverse_to_favorite"):
                raise ValueError("critical spine severity requires adverse roster evidence")
            families[fam]={"source_id":sid,"observed_at":stamp,"state":state,
                           "critical_spine_severe":severe,"origin":"explicit_favorite_relative"}
            critical=critical or severe
    elif legacy is not None:
        if not isinstance(legacy,list): raise ValueError("risk_evidence must be a list")
        for rec in legacy:
            if not isinstance(rec,dict): raise ValueError("risk_evidence item must be an object")
            alias=rec.get("family")
            if alias not in FAMILY_GROUP: raise ValueError(f"unsupported risk evidence family: {alias}")
            fam=FAMILY_GROUP[alias]
            if fam in families: raise ValueError(f"correlated risk evidence duplicated within {fam}")
            sid,stamp=_time_record(rec,f"risk_evidence.{alias}",cutoff)
            state=rec.get("state")
            if state not in ("adverse_to_home","neutral","favorable_to_home"):
                raise ValueError("legacy risk state must be home-relative")
            if side=="home":
                fav_state={"adverse_to_home":"adverse_to_favorite","neutral":"neutral","favorable_to_home":"favorable_to_favorite"}[state]
            else:
                fav_state={"adverse_to_home":"favorable_to_favorite","neutral":"neutral","favorable_to_home":"adverse_to_favorite"}[state]
            severe=bool(rec.get("critical_spine_severe",False)) if side=="home" else False
            families[fam]={"source_id":sid,"observed_at":stamp,"state":fav_state,
                           "critical_spine_severe":severe,
                           "origin":"legacy_home_relative_inverted" if side=="away" else "legacy_home_relative"}
            critical=critical or severe
    # Complete ESR is merged into the roster family even when an explicit roster
    # record exists. It can strengthen a critical warning but never add a second vote.
    if functionality.get("status") in ("CONFIRMED_BOTH","PROJECTED_AT_LEAST_ONE"):
        align=functionality.get("alignment")
        if align in ("DUAL_ADVERSE_TO_RAW_DIRECTION","ADVERSE_COMPONENT_REVIEW"): derived_state="adverse_to_favorite"
        elif align=="DUAL_SUPPORTS_RAW_DIRECTION": derived_state="favorable_to_favorite"
        else: derived_state="neutral"
        squads=packet.get("squads",{})
        src=squads.get("home",{}).get("minutes_source",{}) if isinstance(squads,dict) else {}
        severe=bool(set(functionality.get("flags",[])) & {
            "RAW_DIRECTION_GOALKEEPER_REPLACEMENT_QUALITY_DROP","RAW_DIRECTION_DEFENSIVE_SPINE_QUALITY_DROP"})
        if "roster" not in families:
            families["roster"]={"source_id":src.get("source_id","ESR_DERIVED_ROSTER"),
                "observed_at":src.get("observed_at",packet["cutoff"]),"state":derived_state,
                "critical_spine_severe":severe,"origin":"derived_from_ESR_one_roster_family"}
        else:
            existing=families["roster"]
            if derived_state=="adverse_to_favorite": existing["state"]="adverse_to_favorite"
            existing["esr_role_alignment"]=derived_state
            existing["esr_role_flags"]=functionality.get("flags",[])
            existing["critical_spine_severe"]=bool(existing.get("critical_spine_severe") or severe)
            existing["origin"] += "+ESR_same_roster_family"
        critical=critical or severe
    adverse=sum(x["state"]=="adverse_to_favorite" for x in families.values())
    favorable=sum(x["state"]=="favorable_to_favorite" for x in families.values())
    if critical: status="HIGH_RISK_CRITICAL_ROSTER_TO_RAW_DIRECTION"
    elif adverse>=2: status="HIGH_RISK_TWO_INDEPENDENT_FAMILIES"
    elif adverse==1: status="WATCH_ONE_ADVERSE_FAMILY"
    elif len(families)<2: status="UNKNOWN_INSUFFICIENT_DIRECTIONAL_EVIDENCE"
    else: status="REVIEWED_NO_ADVERSE_FAMILY"
    stakes=parent.get("raw_direction_stakes_context","UNKNOWN")
    msi=parent.get("objective_stakes_MSI",{})
    mflags=[]
    if stakes=="OPPONENT_HIGH_STAKES": mflags.append("OPPONENT_OBJECTIVE_STAKES_EDGE_REVIEW")
    if parent.get("intent_capacity_conflict"): mflags.append("HIGH_INTENT_LOWER_EFFECTIVE_CAPACITY")
    if msi.get("status")!="VERIFIED_BOTH": mflags.append("MSI_CONTEXT_INCOMPLETE_NOT_A_WIN_PROBABILITY")
    return {"version":"DVRG_v0.1","status":status,"raw_direction":raw_direction,
            "direction_side":side,"top1_probability":round(top1,6),
            "independent_families":families,"family_count":len(families),
            "adverse_family_count":adverse,"favorable_family_count":favorable,
            "critical_roster_risk":critical,"motivation_context_flags":mflags,
            "authorization_effect":"HOLD_CORE_HIGH_RISK" if status.startswith("HIGH_RISK") else
              "WATCH_CORE" if status.startswith("WATCH") else
              "HOLD_CORE_EVIDENCE_INCOMPLETE" if status.startswith("UNKNOWN") else "NO_EXTRA_CORE_HOLD",
            "single_direction_retained":raw_direction,"probability_adjustment":False,
            "automatic_direction_flip":False,"motivation_counted_as_risk_family":False}


def _selection_efficiency_v05(packet: dict, parent: dict, gate: dict) -> dict:
    p=parent["outcome_probabilities_unchanged"]; ranked=r636._rank_wdl(p)
    top1,second,third=(p[i] for i in ranked); gap=top1-second; level=packet.get("research_selection_level")
    allowed=(None,"core_candidate","hot_favorite_review","observation","avoid","核心候选","热门二审","观察","规避")
    if level not in allowed: raise ValueError("unsupported research_selection_level")
    if top1<.40 or gap<=.03: state="WEAK_EDGE_DIRECTION_ONLY"
    elif top1>=.60 and gap>=.15: state="STRONG_DIRECTION_REVIEW"
    elif top1>=.50 and gap>=.05: state="MODERATE_DIRECTION_REVIEW"
    else: state="NARROW_EDGE_DIRECTION_ONLY"
    avoid=level in ("avoid","规避"); recovery=avoid and top1>=.35 and gap<=.08
    if recovery and gate.get("status","").startswith("HIGH_RISK"): rec_status="KEEP_HOLD_HIGH_RISK_NOT_RECOVERY"
    elif recovery and gate.get("status","").startswith("UNKNOWN"): rec_status="REVIEW_AVOIDED_TOP1_WITH_DATA_GAP_NO_AUTO_RESTORE"
    elif recovery: rec_status="REVIEW_AVOIDED_TOP1_OPPORTUNITY_NO_AUTO_RESTORE"
    else: rec_status="NO_AVOIDANCE_RECOVERY_TRIGGER"
    core="NOT_REQUESTED"
    if level in ("core_candidate","核心候选"):
        if gate.get("status","").startswith("HIGH_RISK"): core="HOLD_CORE_HIGH_RISK"
        elif gate.get("status","").startswith("UNKNOWN"): core="HOLD_CORE_EVIDENCE_INCOMPLETE"
        elif gate.get("status","").startswith("WATCH"): core="WATCH_CORE_ONE_ADVERSE_FAMILY"
        elif top1<.60 or gap<.15: core="HOLD_CORE_WEAK_PROBABILITY_STRUCTURE"
        elif parent.get("effective_squad_ESR",{}).get("status")!="CONFIRMED_BOTH": core="HOLD_CORE_LINEUP_NOT_BOTH_CONFIRMED"
        elif parent.get("objective_stakes_MSI",{}).get("status")!="VERIFIED_BOTH": core="HOLD_CORE_MSI_INCOMPLETE"
        elif not parent.get("research_core_context_review_pass",False): core="HOLD_CORE_R634_CONTEXT_GATE"
        else: core="RESEARCH_CORE_REVIEW_READY_NOT_GRANTED"
    return {"version":"Selection_Efficiency_v0.5","raw_direction":WDL[ranked[0]],
            "top1_probability":round(top1,6),"top1_minus_second_gap":round(gap,6),
            "direction_state":state,"research_selection_level":level,
            "direction_vulnerability_status":gate.get("status"),"core_candidate_review":core,
            "avoidance_recovery_review":rec_status,"single_direction_retained":WDL[ranked[0]],
            "formal_single_grant":None,"formal_core_grant":None,
            "probability_adjustment":False,"automatic_direction_flip":False}


def _score_family_audit_v15(packet: dict, parent: dict, exact_tail: dict) -> dict:
    matrix=packet.get("score_matrix"); audit=parent.get("GS1_3_joint_score_audit",{})
    if not matrix or audit.get("status")!="JOINT_MATRIX_COHERENT":
        return {"version":"GS1.5","status":"UNKNOWN_NO_COHERENT_SCORE_MATRIX",
                "score_top3":None,"result_family_top2":None,"total_bucket_best_scores":None,
                "probability_adjustment":False}
    ordered=sorted(matrix,key=lambda x:(-float(x["probability"]),x["score"]))
    top3=[x["score"] for x in ordered[:3]]
    result_rows={k:[] for k in WDL}; total_rows={str(i):[] for i in range(7)}; total_rows["7+"]=[]
    for row in matrix:
        h,a=(int(v) for v in row["score"].split(":")); outcome="胜" if h>a else "平" if h==a else "负"
        total=h+a; bucket=str(total) if total<=6 else "7+"
        result_rows[outcome].append(row); total_rows[bucket].append(row)
    def topn(rows,n):
        rows=sorted(rows,key=lambda x:(-float(x["probability"]),x["score"]))[:n]
        return [{"score":x["score"],"probability":float(x["probability"])} for x in rows]
    result_top2={k:topn(v,2) for k,v in result_rows.items() if v}
    total_best={k:topn(v,1)[0] for k,v in total_rows.items() if v}
    multi_draw=[x for x in result_top2.get("平",[]) if sum(int(v) for v in x["score"].split(":"))>=4]
    tails={k:v for k,v in total_best.items() if k in ("5","6","7+")}; flags=[]
    if multi_draw and not any(x["score"] in top3 for x in multi_draw): flags.append("MULTI_GOAL_DRAW_SCORE_OUTSIDE_SCORE_TOP3_REVIEW")
    if "7+" in tails and tails["7+"]["score"] not in top3: flags.append("7PLUS_SCORE_FAMILY_OUTSIDE_SCORE_TOP3_REVIEW")
    exact=exact_tail.get("exact_tail_bucket")
    top_buckets={str(sum(int(v) for v in s.split(":"))) if sum(int(v) for v in s.split(":"))<=6 else "7+" for s in top3}
    if exact_tail.get("status")=="EXACT_BUCKET_ONE_SLOT" and exact not in top_buckets:
        flags.append("RC25_EXACT_GOAL_TAIL_NOT_REPRESENTED_IN_SCORE_TOP3")
    return {"version":"GS1.5","status":"SCORE_FAMILY_RUNNER_UP_AUDITED",
            "score_top3":top3,"score_top3_unchanged":True,"result_family_top2":result_top2,
            "draw_multi_goal_watch":multi_draw,"total_bucket_best_scores":total_best,
            "high_tail_score_candidates":tails,"flags":flags,
            "ranking_changed":False,"probability_adjustment":False}


def _handicap_contract_v17(packet: dict, parent: dict) -> dict:
    """Require timestamped official JC integer line and frozen unique pick; never accept Asian line."""
    line=packet.get("official_handicap_line"); source=packet.get("official_handicap_line_source"); pick=packet.get("frozen_handicap_pick")
    if line is None or source is None or pick is None:
        return {"version":"S4_v1.7","status":"UNKNOWN_MISSING_OFFICIAL_INTEGER_LINE_SOURCE_OR_FROZEN_PICK",
                "official_handicap_line":None,"frozen_handicap_pick":None,"research_top1":None,
                "accuracy_scored":False,"asian_handicap_substitution_forbidden":True}
    if type(line) is not int or line < -3 or line > 3: raise ValueError("official_handicap_line must be an integer from -3 to +3")
    if pick not in ("让胜","让平","让负"): raise ValueError("frozen_handicap_pick must be one unique JC handicap outcome")
    cutoff=base._time(packet["cutoff"],"cutoff"); sid,stamp=_time_record(source,"official_handicap_line_source",cutoff)
    if source.get("basis")!="official_jc_handicap": raise ValueError("official handicap line source basis must be official_jc_handicap")
    if packet.get("home_handicap_line") is not None and packet["home_handicap_line"]!=line:
        raise ValueError("home_handicap_line conflicts with official_handicap_line; Asian handicap cannot substitute")
    pcopy=dict(packet); pcopy["home_handicap_line"]=line
    audit=r636._handicap_audit(pcopy,parent["outcome_probabilities_unchanged"])
    return {"version":"S4_v1.7",**audit,"official_handicap_line":line,
            "official_handicap_source_id":sid,"official_handicap_observed_at":stamp,
            "frozen_handicap_pick":pick,
            "pick_matches_research_top1":audit.get("research_top1")==pick if audit.get("research_top1") else None,
            "accuracy_scored":False,"asian_handicap_substitution_forbidden":True}


def inspect(packet: dict) -> dict:
    parent=r636.inspect(packet); probabilities=parent["outcome_probabilities_unchanged"]
    raw=WDL[r636._rank_wdl(probabilities)[0]]
    functionality=_role_functionality(parent,raw)
    gate=_direction_vulnerability_gate(packet,parent,raw,probabilities,functionality)
    selection=_selection_efficiency_v05(packet,parent,gate)
    score_family=_score_family_audit_v15(packet,parent,parent["RC2_5_exact_bucket_router"])
    handicap=_handicap_contract_v17(packet,parent)
    flags=list(parent.get("audit_flags_r636",[]))
    if gate["status"].startswith("HIGH_RISK"): flags.append("DVRG_DIRECTIONAL_HIGH_RISK_CORE_HOLD")
    if gate["status"].startswith("UNKNOWN"): flags.append("DVRG_DIRECTIONAL_EVIDENCE_INCOMPLETE_CORE_HOLD")
    flags.extend(functionality.get("flags",[])); flags.extend(score_family.get("flags",[]))
    if handicap.get("status","").startswith("UNKNOWN"): flags.append("S4_V17_OFFICIAL_JC_HANDICAP_INPUT_MISSING")
    return {**parent,"version":VERSION,"ESR_Functionality_v0_1":functionality,
            "DVRG_v0_1":gate,"Selection_Efficiency_v0_5":selection,
            "GS1_5_score_family_runner_up_audit":score_family,
            "S4_v1_7_official_handicap_contract":handicap,
            "audit_flags_r637":flags,"outcome_probabilities_unchanged":probabilities,
            "probability_adjustment_applied":False,"automatic_direction_flip":False,
            "formal_single_grant":None,"formal_core_grant":None,"formal_protection_grant":None,
            "formal_handicap_grant":None,"production_changed":False,
            "notes_r637":[
              "M79.3.6 Production remains frozen; R6.3.7 is Shadow only.",
              "DVRG reviews home and away raw directions symmetrically; unknown evidence holds core review only, not the unique raw direction.",
              "ESR goalkeeper, defensive-spine and attacking-unit shifts are components of one roster family, never three independent votes.",
              "MSI pressure is context, not a win-probability boost or an independent risk-family vote.",
              "GS1.5 adds result-family runner-ups and goal-bucket score candidates; original Score Top3 and probabilities remain unchanged.",
              "S4 v1.7 requires a timestamped official Chinese lottery integer handicap and a frozen unique pick; Asian handicap is not accepted.",
              "RC2.5 and HT-State v0.3 are inherited unchanged; no thresholds are fitted to the 25-match conversation recap.",
              "Post-match scores, cards and in-play events are prohibited in prematch inspect()."]}


def replay_conversation_recap25(rows: list[dict]) -> dict:
    """Descriptive arithmetic only for 25 published prematch rows; not training/holdout."""
    if not isinstance(rows,list) or len(rows)!=25: raise ValueError("exactly 25 recap rows required")
    seen=set(); keys=("single","protection","goals_top3","score_top3","half_full_top2")
    hits={k:0 for k in keys}; misses={k:[] for k in keys}; per=[]
    for row in rows:
        rid=row.get("id")
        if not isinstance(rid,str) or rid in seen: raise ValueError("unique string id required")
        seen.add(rid); ft=row.get("actual_score"); ht=row.get("half_time_score")
        for label,score in (("actual_score",ft),("half_time_score",ht)):
            if not isinstance(score,list) or len(score)!=2 or any(type(x) is not int or x<0 for x in score): raise ValueError(f"{label} must be nonnegative integer pair")
        actual="胜" if ft[0]>ft[1] else "平" if ft[0]==ft[1] else "负"
        half="胜" if ht[0]>ht[1] else "平" if ht[0]==ht[1] else "负"
        htft=half+actual; total=sum(ft); bucket=str(total) if total<=6 else "7+"
        if row.get("single") not in WDL: raise ValueError("single must be a unique WDL choice")
        protection=row.get("protection")
        if not isinstance(protection,list) or len(protection)!=2 or len(set(protection))!=2 or not set(protection).issubset(WDL): raise ValueError("protection must be two distinct WDL choices")
        if row["single"] not in protection: raise ValueError("protection must contain the unique single")
        goals=row.get("goal_top3"); scores=row.get("score_top3"); htfts=row.get("half_full_top2")
        if not isinstance(goals,list) or len(goals)!=3: raise ValueError("goal_top3 must contain three buckets")
        if not isinstance(scores,list) or len(scores)!=3: raise ValueError("score_top3 must contain three scores")
        if not isinstance(htfts,list) or len(htfts)!=2: raise ValueError("half_full_top2 must contain two states")
        actual_score=f"{ft[0]}:{ft[1]}"
        rowhits={"single":row["single"]==actual,"protection":actual in protection,
                 "goals_top3":bucket in [str(x) for x in goals],"score_top3":actual_score in scores,
                 "half_full_top2":htft in htfts}
        for k,v in rowhits.items():
            hits[k]+=int(v)
            if not v: misses[k].append(rid)
        per.append({"id":rid,"actual_score":actual_score,"actual_wdl":actual,"actual_htft":htft,
                    "actual_total_bucket":bucket,"hits":rowhits})
    n=len(rows); metrics={k:{"hits":hits[k],"n":n,"rate":hits[k]/n,"misses":misses[k]} for k in keys}
    return {"version":VERSION,"dataset":"PUBLISHED_CONVERSATION_RECAP_ONLY_NOT_OFFICIAL_FROZEN_NOT_HOLDOUT",
            "n":n,"metrics":metrics,"handicap_metric":None,
            "handicap_reason":"No complete frozen official integer handicap line plus unique pick was published for all 25 matches.",
            "training_or_threshold_fit":False,"independent_validation":False,"probability_scores":None,
            "correction_note":"Half/full Top2 was recomputed as 16/25, correcting the prior narrative's 17/25 arithmetic.",
            "per_match":per,"notes":[
              "Descriptive arithmetic only; input is reconstructed from the published conversation, not an official prematch freeze archive.",
              "Do not fit thresholds or claim independent performance from this batch.",
              "The 018/019/021 tail misses are not grounds to increase all high-tail probabilities.",
              "Handicap performance is not scored without a frozen official JC integer line and pick."]}
