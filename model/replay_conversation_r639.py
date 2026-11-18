"""Descriptive audit of six prior chat-reference predictions. NOT a model backtest.
Never used as an input to shadow_r639.inspect() or to fit parameters.
"""
from __future__ import annotations
from shadow_r639 import _score


def audit_recap(rows: list[dict]) -> dict:
    if not isinstance(rows,list) or len(rows)!=6: raise ValueError("six chat reference rows required")
    seen=set(); out=[]
    for r in rows:
        mid=r.get("id")
        if mid not in ("001","002","003","004","005","006") or mid in seen:
            raise ValueError("duplicate or invalid recap match id")
        seen.add(mid)
        h,a=_score(r["actual_score"])
        actual_wdl="胜" if h>a else "平" if h==a else "负"
        line=r["official_handicap_line"]
        if type(line) is not int: raise ValueError("official integer line required")
        bet="让胜" if h+line>a else "让平" if h+line==a else "让负"
        selection=r["single"]
        pair=r["protection"]
        if selection not in ("胜","平","负") or type(pair) is not list or len(pair)!=2 or len(set(pair))!=2 or selection not in pair:
            raise ValueError("recap WDL/pair invalid")
        if r["jc_pick"] not in ("让胜","让平","让负"):
            raise ValueError("jc pick invalid")
        goals=r["goals_top3"]; scores=r["scores_top3"]
        if len(goals)!=3 or len(set(goals))!=3 or any(type(g) is not int or g<0 for g in goals):
            raise ValueError("goals_top3 requires three unique exact integer totals")
        if len(scores)!=3 or len(set(scores))!=3:
            raise ValueError("scores_top3 requires three unique scorelines")
        for score in scores: _score(score)
        if type(r["ordinary_sale"]) is not bool: raise ValueError("ordinary_sale explicit boolean required")
        out.append({"id":mid,"actual_score":r["actual_score"],"actual_wdl":actual_wdl,
                    "actual_jc":bet,"ordinary_sale":r["ordinary_sale"],
                    "unique_hit":selection==actual_wdl,
                    "protection_hit":actual_wdl in pair,
                    "jc_hit":r["jc_pick"]==bet,
                    "goals_top3_hit":h+a in goals,
                    "score_top3_hit":r["actual_score"] in scores,
                    "score_top1_hit":r["actual_score"]==scores[0]})
    out.sort(key=lambda x:x["id"])
    def rates(filtered):
        return {k:{"hits":sum(bool(x[k]) for x in filtered),"n":len(filtered)} for k in
                ("unique_hit","protection_hit","jc_hit","goals_top3_hit","score_top3_hit","score_top1_hit")}
    available=[x for x in out if x["ordinary_sale"]]
    return {"status":"CONVERSATION_REFERENCE_ONLY_NOT_OFFICIALLY_FROZEN_NOT_HOLDOUT",
            "date":"2026-11-12", "production_score_eligible":False,
            "training_or_calibration_performed":False,
            "all_research_directions":rates(out),"ordinary_sale_subset":rates(available),
            "let_draw_actual_count":sum(x["actual_jc"]=="让平" for x in out),
            "rows":out}
