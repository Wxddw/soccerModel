"""R6.3.6 2026-11-21 research-only matchday publishing gates.

Do not change Production M79.3.6; never train on the completed eight-match casebook.
This layer validates a proposed prematch report against one complete frozen Q.
"""
from __future__ import annotations
from datetime import datetime
import math

WDL = ("胜", "平", "负")
HTFT = tuple(h + f for h in WDL for f in WDL)
GOALS = tuple(str(x) for x in range(7)) + ("7+",)
EVIDENCE_FAMILIES = {"market", "roster", "schedule", "tactics", "weather", "motivation"}


def _dt(value):
    if not isinstance(value, str):
        raise ValueError("timestamp with timezone required")
    try:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("invalid timestamp") from e
    if out.tzinfo is None or out.utcoffset() is None:
        raise ValueError("naive timestamp prohibited")
    return out


def _score_grid(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("complete frozen score grid required")
    seen = set()
    out = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"score", "probability"}:
            raise ValueError("score grid schema mismatch or postmatch field")
        val = row["score"]
        if not isinstance(val, str) or ":" not in val:
            raise ValueError("score H:A required")
        parts = val.split(":")
        if len(parts) != 2 or any(not s.isdigit() or str(int(s)) != s for s in parts):
            raise ValueError("canonical nonnegative score required")
        h, a = (int(s) for s in parts)
        p = row["probability"]
        if (h, a) in seen or type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError("invalid or duplicate frozen score cell")
        seen.add((h, a))
        out.append((h, a, float(p)))
    if not math.isclose(math.fsum(p for _, _, p in out), 1., rel_tol=0, abs_tol=1e-8):
        raise ValueError("missing Q tail mass: never normalize truncated score Top3")
    return out


def _wdl(h, a):
    return "胜" if h > a else "平" if h == a else "负"


def _rank(probs):
    return sorted(probs, key=lambda x: (-probs[x], x))


def _source_time(record, cutoff, name):
    if not isinstance(record, dict) or set(record) != {"source_id", "observed_at"}:
        raise ValueError(f"{name}: source_id and observed_at required")
    if not isinstance(record["source_id"], str) or not record["source_id"].strip():
        raise ValueError(f"{name}: source_id missing")
    if _dt(record["observed_at"]) > cutoff:
        raise ValueError(f"{name}: postcutoff evidence blocked")


def review(packet):
    """Static prematch cross-layer audit, no official selections or odds calibration."""
    required = {"match_id", "kickoff", "cutoff", "q_observation", "score_grid", "frozen_wdl",
                "published_score_top3", "published_goal_top3", "published_htft",
                "htft_probabilities", "official_jc_line", "jc_observation", "evidence",
                "market_home_buy_share", "market_buy_observation", "publication_observation",
                "reversal_proposal", "reversal_policy"}
    if not isinstance(packet, dict) or set(packet) != required:
        raise ValueError("complete prematch packet only: unexpected/missing fields blocked")
    match_id = packet["match_id"]
    if not isinstance(match_id, str) or not match_id.strip():
        raise ValueError("match_id required")
    cutoff, kickoff = _dt(packet["cutoff"]), _dt(packet["kickoff"])
    if cutoff >= kickoff:
        raise ValueError("prematch cutoff must precede kickoff")
    _source_time(packet["q_observation"], cutoff, "Q")
    _source_time(packet["publication_observation"], cutoff, "published predictions")
    line = packet["official_jc_line"]
    if line is not None:
        if type(line) is not int or not -3 <= line <= 3:
            raise ValueError("official JC signed INTEGER -3..+3 required")
        _source_time(packet["jc_observation"], cutoff, "JC")
    elif packet["jc_observation"] is not None:
        raise ValueError("JC source cannot imply an unstated official line")
    frozen = packet["frozen_wdl"]
    if frozen not in WDL:
        raise ValueError("one frozen WDL pick required")
    cells = _score_grid(packet["score_grid"])
    wdl = {x: 0. for x in WDL}
    jc = {x: 0. for x in ("让胜", "让平", "让负")} if line is not None else None
    goals = {x: 0. for x in GOALS}
    margin = {}
    for h, a, p in cells:
        wdl[_wdl(h, a)] += p
        d = h-a
        margin[d] = margin.get(d, 0.) + p
        goals[str(h+a) if h+a <= 6 else "7+"] += p
        if jc is not None:
            adjusted = d + line
            jc["让胜" if adjusted > 0 else "让平" if adjusted == 0 else "让负"] += p
    if not isinstance(packet["published_score_top3"], list):
        raise ValueError("published scores must be a list")
    actual_score_top3 = [f"{h}:{a}" for h, a, p in sorted(cells, key=lambda row: (-row[2], row[0], row[1]))[:3]]
    actual_goals_top3 = _rank(goals)[:3]
    score_report = packet["published_score_top3"]
    goal_report = packet["published_goal_top3"]
    if (not isinstance(score_report, list) or len(score_report) != 3 or len(set(score_report)) != 3
        or not isinstance(goal_report, list) or len(goal_report) != 3 or len(set(goal_report)) != 3
        or any(v not in GOALS for v in goal_report)):
        raise ValueError("published score/goal Top3 needs three distinct values")
    for v in score_report:
        if v not in {f"{h}:{a}" for h,a,p in cells}:
            raise ValueError("published score candidate outside complete frozen grid")
    htft = packet["htft_probabilities"]
    ht_status = "NO_FROZEN_NINE_CLASS_DISTRIBUTION"
    nine = None
    if htft is not None:
        if (not isinstance(htft, dict) or set(htft) != set(HTFT)
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 or v > 1 for v in htft.values())
            or abs(math.fsum(htft.values())-1) > 1e-8):
            raise ValueError("invalid frozen HTFT 9-class distribution")
        for f in WDL:
            if abs(math.fsum(htft[h+f] for h in WDL) - wdl[f]) > 1e-8:
                raise ValueError("HTFT FT marginal disagrees with frozen Q")
        nine = dict(htft)
        ht_status = "Q_MARGINALS_MATCHED_SHADOW_ONLY"
    published_htft = packet["published_htft"]
    if not isinstance(published_htft, list) or len(published_htft) != 2 or len(set(published_htft)) != 2 or any(x not in HTFT for x in published_htft):
        raise ValueError("half/full must have exactly two distinct recognized choices")
    facts = packet["evidence"]
    if not isinstance(facts, list):
        raise ValueError("evidence must be a list")
    evidence_groups = {}
    evidence_sources = {}
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {"family", "impact", "source_id", "observed_at"}:
            raise ValueError("invalid evidence schema")
        if fact["family"] not in EVIDENCE_FAMILIES or fact["impact"] not in ("adverse", "favorable", "neutral"):
            raise ValueError("invalid evidence family/impact")
        _source_time({"source_id":fact["source_id"], "observed_at":fact["observed_at"]}, cutoff, "evidence")
        evidence_groups.setdefault(fact["family"], set()).add(fact["impact"])
        if fact["impact"] == "adverse":
            evidence_sources.setdefault(fact["family"], set()).add(fact["source_id"])
    # Multiple odds/transaction rows cannot count as distinct corroborating evidence.
    adverse_nonmarket = [f for f, impacts in evidence_groups.items() if f != "market" and "adverse" in impacts]
    independent_source_count = len(set().union(*(evidence_sources[f] for f in adverse_nonmarket))) if adverse_nonmarket else 0
    proposal = packet["reversal_proposal"]
    if proposal is not None and (proposal not in WDL or proposal == frozen):
        raise ValueError("reversal proposal must differ from original WDL")
    policy = packet["reversal_policy"]
    policy_pre_registered = False
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) != {"source_id", "registered_at", "minimum_gap"}:
            raise ValueError("reversal policy must be source-registered")
        gap = policy["minimum_gap"]
        if type(gap) not in (int, float) or not math.isfinite(gap) or not 0 <= gap <= 1:
            raise ValueError("invalid preregistered outcome gap")
        if not isinstance(policy["source_id"], str) or not policy["source_id"].strip():
            raise ValueError("policy source required")
        policy_pre_registered = _dt(policy["registered_at"]) <= cutoff
    eligible_reversal_review = bool(proposal is not None and policy_pre_registered
       and len(adverse_nonmarket) >= 2 and independent_source_count >= 2 and wdl[proposal] - wdl[frozen] >= policy["minimum_gap"])
    share = packet["market_home_buy_share"]
    if share is not None:
        if type(share) not in (int, float) or not math.isfinite(share) or not 0 <= share <= 1:
            raise ValueError("market buy share must be 0..1")
        _source_time(packet["market_buy_observation"], cutoff, "market buy share")
    elif packet["market_buy_observation"] is not None:
        raise ValueError("buy-share source without a reported value")
    warnings = []
    if frozen != max(WDL, key=lambda k: wdl[k]):
        warnings.append("FROZEN_WDL_DIFFERS_FROM_JOINT_MATRIX_TOP1_NO_AUTO_FLIP")
    if score_report != actual_score_top3:
        warnings.append("PUBLISHED_SCORE_TOP3_DIFFERS_FROM_FROZEN_Q")
    if goal_report != actual_goals_top3:
        warnings.append("PUBLISHED_GOAL_TOP3_DIFFERS_FROM_FROZEN_Q")
    if any(x in actual_goals_top3 and x not in goal_report for x in ("2", "3")):
        warnings.append("CENTRAL_2_3_DISPLACEMENT_REQUIRES_REVIEW")
    if any(x in actual_goals_top3 and x not in goal_report for x in ("0", "1", "4", "5", "6", "7+")):
        warnings.append("TAIL_OR_FOUR_GOAL_BIN_MISSING_FROM_PUBLISHED_TOP3")
    if nine is None:
        warnings.append("HTFT_NO_CERTIFIED_Q_COHERENT_NINE_CLASS_DISTRIBUTION")
    elif published_htft != _rank(nine)[:2]:
        warnings.append("PUBLISHED_HTFT_TOP2_NOT_PROBABILITY_RANKED")
    if share is not None and share >= .8 and wdl["胜"] < .70:
        warnings.append("HOME_BUY_SHARE_HIGH_RELATIVE_TO_MODEL_PROB_REVIEW_ONLY")
    if jc is not None and sorted(jc.values(),reverse=True)[0] - sorted(jc.values(),reverse=True)[1] <= .05:
        warnings.append("JC_TOP2_NARROW_GAP_REVIEW_ONLY")
    if proposal is not None and not eligible_reversal_review:
        warnings.append("REVERSAL_NOT_ELIGIBLE_FOR_MANUAL_REVIEW")
    component_gates = {
        "Outcome": "REVIEW_FROZEN_VS_Q" if frozen != max(WDL, key=lambda k:wdl[k]) else "SHADOW_CONSISTENT",
        "Score": "BLOCK_TOP3_NOT_Q_DERIVED" if score_report != actual_score_top3 else "SHADOW_CONSISTENT",
        "Goal": "BLOCK_TOP3_NOT_Q_DERIVED" if goal_report != actual_goals_top3 else "SHADOW_CONSISTENT",
        "HTFT": ("BLOCK_NO_NINE_CLASS" if nine is None else
                 "BLOCK_TOP2_NOT_Q_RANKED" if published_htft != _rank(nine)[:2] else "SHADOW_CONSISTENT"),
        "JC": "BLOCK_OFFICIAL_LINE_MISSING" if line is None else "SHADOW_CONSISTENT",
    }
    central_rank = {"2": actual_goals_top3.index("2") if "2" in actual_goals_top3 else None,
                    "3": actual_goals_top3.index("3") if "3" in actual_goals_top3 else None}
    return {"research_only": True, "formal_grant": None, "status":"SHADOW_PREMATCH_REVIEW",
        "match_id": match_id, "wdl": wdl,"frozen_wdl":frozen,
        "score_top3_derived":actual_score_top3, "goal_top3_derived":actual_goals_top3,
        "goal_buckets":goals,
        "goal_tail_diagnostics":{"low_0":goals["0"], "low_1":goals["1"],
            "edge_4":goals["4"],"high_5":goals["5"],"high_6":goals["6"],"high_7plus":goals["7+"],"central_2_3_rank":central_rank},
        "margin_plus_one":margin.get(1,0.), "margin_plus_two":margin.get(2,0.),
        "exact_margin":dict(sorted(margin.items())),
        "official_jc_line":line,"jc":jc,
        "htft_status":ht_status, "htft_top2_from_nine":_rank(nine)[:2] if nine else None,
        "market_buy_share":share, "reversal_review_eligible":eligible_reversal_review,
        "independent_adverse_nonmarket_families":sorted(adverse_nonmarket),
        "component_release_gates":component_gates,
        "warnings":warnings, "production_mutated":False}


def batch_concentration(reviews, *, published_htft=None):
    """Batch-level exposure monitoring only. Does NOT flip or penalize WDL scores."""
    if not isinstance(reviews,list) or not reviews:
        raise ValueError("nonempty reviewed prematch batch required")
    if any(not isinstance(r,dict) or r.get("status")!="SHADOW_PREMATCH_REVIEW" for r in reviews):
        raise ValueError("batch must contain validated prematch reviews")
    ids=[r["match_id"] for r in reviews]
    if len(set(ids))!=len(ids):raise ValueError("duplicate match ids")
    counts={x:sum(r["frozen_wdl"]==x for r in reviews) for x in WDL}
    hhi=sum((v/len(reviews))**2 for v in counts.values())
    flags=[]
    if len(reviews)>=5 and counts["胜"] / len(reviews)>=.8:
        flags.append("EXCESS_HOME_WDL_CONCENTRATION_REVIEW_ONLY")
    ht_counts=None
    if published_htft is not None:
        if not isinstance(published_htft,list) or len(published_htft)!=len(reviews) or any(v not in HTFT for v in published_htft):
            raise ValueError("aligned HTFT Top1 list required")
        ht_counts={x:published_htft.count(x) for x in HTFT}
        if len(reviews)>=5 and (ht_counts["平胜"]+ht_counts["胜胜"])/len(reviews)>=.8:
            flags.append("EXCESS_HALFTIME_TO_HOME_WIN_CONCENTRATION_REVIEW_ONLY")
    return {"research_only":True,"formal_grant":None,"n":len(reviews),
        "wdl_counts":counts,"wdl_hhi":hhi,"htft_top1_counts":ht_counts,
        "flags":flags,"change_any_pick":False}


def published_only_bias(records):
    """Audit chat's already-published selections without fabricating a frozen Q."""
    if not isinstance(records, list) or not records:
        raise ValueError("nonempty publication records required")
    ids = set()
    formal = {x: 0 for x in WDL}
    scenario = {x: 0 for x in HTFT}
    sale = 0
    for rec in records:
        if not isinstance(rec, dict) or set(rec) != {"match_id", "ordinary_offered", "frozen_wdl", "htft_primary"}:
            raise ValueError("publication records require exact fields, never scores")
        if rec["match_id"] in ids or not isinstance(rec["match_id"], str) or not rec["match_id"]:
            raise ValueError("duplicate/invalid match id")
        ids.add(rec["match_id"])
        if type(rec["ordinary_offered"]) is not bool or rec["frozen_wdl"] not in WDL or rec["htft_primary"] not in HTFT:
            raise ValueError("invalid offered market or published choice")
        if rec["ordinary_offered"]:
            formal[rec["frozen_wdl"]] += 1
            sale += 1
        scenario[rec["htft_primary"]] += 1
    warnings = []
    if sale >= 5 and formal["胜"] / sale >= .8:
        warnings.append("ORDINARY_HOME_SINGLE_OVERCONCENTRATED")
    if len(records) >= 5 and (scenario["胜胜"] + scenario["平胜"]) / len(records) >= .8:
        warnings.append("HTFT_HOME_FINISH_OVERCONCENTRATED")
    return {"research_only": True, "formal_grant": None, "no_joint_q_claim": True,
        "n":len(records), "ordinary_offered_n":sale,
        "formal_wdl_counts":formal,"htft_primary_counts":scenario,
        "warnings":warnings, "automatic_pick_changes":False}

ROLES = {"GK", "CB", "FB", "DM", "CM", "AM", "W", "ST"}


def audit_aic_availability(rows, *, cutoff, kickoff):
    """Validate *expected* replacement/minutes; actual match events never enter AIC.

    Missing player quality / replacement role generates an advisory, not a
    numeric xG adjustment. Genuine late match injuries must be postmatch-only.
    """
    cut, kick = _dt(cutoff), _dt(kickoff)
    if cut >= kick or not isinstance(rows, list):
        raise ValueError("prematch cutoff and AIC rows required")
    seen = set()
    issues = []
    for rec in rows:
        required = {"player_id", "role", "availability_state", "expected_minutes",
                    "replacement_id", "replacement_role", "source_id", "observed_at"}
        if not isinstance(rec, dict) or set(rec) != required:
            raise ValueError("AIC prediction schema excludes realized injuries/subs/minutes")
        pid = rec["player_id"]
        if not isinstance(pid, str) or not pid or pid in seen:
            raise ValueError("duplicate or invalid AIC player")
        seen.add(pid)
        if rec["role"] not in ROLES or rec["availability_state"] not in ("out", "doubtful", "fit"):
            raise ValueError("invalid prematch player role/status")
        minutes = rec["expected_minutes"]
        if type(minutes) not in (int, float) or not math.isfinite(minutes) or not 0 <= minutes <= 90:
            raise ValueError("expected minutes must be 0..90")
        if rec["availability_state"] == "out" and minutes != 0:
            raise ValueError("out player must have 0 expected minutes")
        repl = rec["replacement_id"]
        repl_role = rec["replacement_role"]
        if repl is not None and (not isinstance(repl, str) or not repl.strip() or repl == pid):
            raise ValueError("replacement identifier invalid")
        if repl_role is not None and repl_role not in ROLES:
            raise ValueError("replacement role invalid")
        if (repl is None) != (repl_role is None):
            raise ValueError("replacement identity and role must both be specified")
        _source_time({"source_id":rec["source_id"],"observed_at":rec["observed_at"]},cut,"AIC")
        if repl is None and rec["availability_state"] != "fit":
            issues.append({"player_id":pid,"flag":"REPLACEMENT_UNCONFIRMED_NO_NUMERIC_EFFECT"})
        if repl is not None and rec["role"] != repl_role:
            issues.append({"player_id":pid,"flag":"POSITION_ROLE_MISMATCH_REVIEW_ONLY"})
    return {"research_only":True,"formal_grant":None,"n":len(rows),
            "issues":issues,"prematch_only":True,"numeric_xg_delta":None}
