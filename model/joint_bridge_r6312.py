"""R6.3.12: probability-conserving map from ONE prematch joint-score grid.

This module never fits, increases or redistributes probability and never
reads match outcomes. An absent JC integer line is unknown, not an Asian line.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re
from typing import Any

WDL = ("胜", "平", "负")
JC = ("让胜", "让平", "让负")
GOALS = tuple(str(k) for k in range(7)) + ("7+",)
EXACT_GOALS = tuple(str(k) for k in range(7))
_SCORE = re.compile(r"^(0|[1-9][0-9]*):(0|[1-9][0-9]*)$")
EPS = 1e-8


def parse_score(s: str) -> tuple[int, int]:
    if not isinstance(s, str) or not _SCORE.fullmatch(s):
        raise ValueError("score must be canonical nonnegative H:A")
    h, a = map(int, s.split(":"))
    if h > 10 or a > 10:
        raise ValueError("score grid supports at most 10 per team; unbounded tails not certified")
    return h, a


def goal_bucket(h: int, a: int) -> str:
    n = h + a
    return str(n) if n < 7 else "7+"


def wdl_label(h: int, a: int) -> str:
    return "胜" if h > a else "平" if h == a else "负"


def jc_label(h: int, a: int, signed_home_line: int) -> str:
    d = h + signed_home_line - a
    return "让胜" if d > 0 else "让平" if d == 0 else "让负"


def _rank(d: dict[str, float], priority: tuple[str, ...]) -> list[str]:
    return sorted(priority, key=lambda k: (-d[k], priority.index(k)))


def aggregate(rows: list[dict], official_jc_integer_line: int | None = None) -> dict:
    """Exact probabilities are never inferred from Top3 alone.

    A complete, normalized score grid is mandatory. No rescaling of an
    incomplete grid or substituting +0.75 Asian lines into JC is allowed.
    """
    if official_jc_integer_line is not None and (
        type(official_jc_integer_line) is not int or
        not -3 <= official_jc_integer_line <= 3
    ):
        raise ValueError("official JC signed line must be integer -3..3")
    if not isinstance(rows, list) or not rows:
        raise ValueError("full nonempty joint score matrix required")
    normalized = []
    seen = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not {"score", "probability"}.issubset(row):
            raise ValueError("each joint row requires score/probability")
        s = row["score"]
        h, a = parse_score(s)
        if s in seen:
            raise ValueError("duplicate score in joint matrix")
        seen.add(s)
        p = row["probability"]
        if type(p) not in (float, int) or not math.isfinite(p) or p < 0 or p > 1:
            raise ValueError("score probability must be finite and within [0,1]")
        normalized.append((s, h, a, float(p)))
    total_mass = math.fsum(p for _, _, _, p in normalized)
    if not math.isclose(total_mass, 1.0, abs_tol=EPS, rel_tol=0):
        raise ValueError("joint grid must sum to 1 without hidden renormalization or truncation")
    wdl = {k: 0.0 for k in WDL}
    goals = {k: 0.0 for k in GOALS}
    margins: dict[int, float] = defaultdict(float)
    jc = {k: 0.0 for k in JC} if official_jc_integer_line is not None else None
    best_goal: dict[str, list[dict]] = {k: [] for k in GOALS}
    global_scores=[]
    for s, h, a, p in normalized:
        w=wdl_label(h,a); goal=goal_bucket(h,a)
        wdl[w]+=p;goals[goal]+=p;margins[h-a]+=p
        label=jc_label(h,a,official_jc_integer_line) if jc is not None else None
        if jc is not None:jc[label]+=p
        r={"score":s,"probability":p,"wdl":w,"goal_bucket":goal,
           "total_goals":h+a,"signed_margin":h-a,"jc":label}
        best_goal[goal].append(r)
        global_scores.append(r)
    # Sorted on *exact score* not on aggregate goal or WDL probabilities.
    by_score=sorted(global_scores,key=lambda r:(-r["probability"],r["score"]))
    score3=by_score[:3]
    goals_rank=_rank(goals,GOALS)
    exact_rank=_rank(goals,EXACT_GOALS)
    jc_rank=None if jc is None else _rank(jc,JC)
    score3_bins={r["goal_bucket"] for r in score3}
    # Coverage matrix reports probability mass, not a logical requirement to
    # force at least one score for each of the three leading goal buckets.
    coverage=[]
    for k in goals_rank[:3]:
        selected=math.fsum(r["probability"] for r in score3 if r["goal_bucket"]==k)
        best=sorted(best_goal[k],key=lambda r:(-r["probability"],r["score"]))
        coverage.append({"goal_bucket":k,"bucket_probability":goals[k],
                         "global_top3_score_mass":selected,
                         "conditional_coverage":selected/goals[k] if goals[k] else None,
                         "highest_exact_score":None if not best else best[0]["score"],
                         "highest_exact_score_probability":None if not best else best[0]["probability"],
                         "represented_in_global_score_top3": k in score3_bins})
    # One optional, read-only Goal-to-Score bridge challenger per missing bucket.
    # Its grid mass is <= global score Top3, never reported as a probability gain.
    score3_mass=math.fsum(r["probability"] for r in score3)
    goal_challengers=[]
    for rec in coverage:
        k=rec["goal_bucket"]
        if rec["represented_in_global_score_top3"] or rec["highest_exact_score"] is None or len(score3)<3:
            continue
        candidate=next(r for r in global_scores if r["score"]==rec["highest_exact_score"])
        alternate=sorted(score3[:2]+[candidate],key=lambda r:(-r["probability"],r["score"]))
        altmass=math.fsum(r["probability"] for r in alternate)
        goal_challengers.append({"missing_goal_bucket":k,
                                 "score_top3_candidate":[r["score"] for r in alternate],
                                 "candidate_mass":altmass,
                                 "loss_vs_unconstrained_global_top3":max(0.,score3_mass-altmass),
                                 "research_only":True,"auto_replace":False})
    signed_margins={str(m):v for m,v in sorted(margins.items())}
    letdraw_target=None if jc is None else -official_jc_integer_line
    letdraw_p=None if jc is None else margins.get(letdraw_target,0.0)
    mapped_top3=[{"score":r["score"],"goal_bucket":r["goal_bucket"],
                  "wdl":r["wdl"],"signed_margin":r["signed_margin"],
                  "jc":r["jc"],"probability":r["probability"]} for r in score3]
    # Fundamental invariants: these MUST hold with no extra choice/weight.
    assert math.isclose(math.fsum(wdl.values()),total_mass,abs_tol=EPS)
    assert math.isclose(math.fsum(goals.values()),total_mass,abs_tol=EPS)
    assert math.isclose(math.fsum(margins.values()),total_mass,abs_tol=EPS)
    if jc is not None:
        assert math.isclose(math.fsum(jc.values()),total_mass,abs_tol=EPS)
        assert math.isclose(jc["让平"],letdraw_p,abs_tol=EPS)
    return {
        "version":"S4_GS_RC_OneJointGrid_R6.3.12",
        "status":"ONE_JOINT_GRID_VALIDATED",
        "joint_mass":total_mass,"grid_score_cells":len(normalized),
        "wdl_probabilities":wdl,"goal_bucket_probabilities":goals,
        "jc_probabilities":jc,"official_signed_jc_line":official_jc_integer_line,
        "signed_margin_distribution":signed_margins,
        "let_draw_margin":letdraw_target,"exact_let_draw_probability":letdraw_p,
        "raw_goal_bucket_top3":goals_rank[:3],
        "raw_integer_0_to_6_top3":exact_rank[:3],
        "raw_score_top3":[r["score"] for r in score3],
        "raw_score_top3_mass":score3_mass,
        "score_top3_cross_layer_mapping":mapped_top3,
        "goal_top3_to_score_top3_coverage":coverage,
        "goal_anchor_challengers":goal_challengers,
        "jc_integrated_rank":jc_rank,
        "seven_plus_aggregate_not_exact_seven":True,
        "score_grid_finite_0_to_10_not_unbounded_tail":True,
        "probability_adjustment":False,"top3_reordered":False,
        "formal_handicap_grant":None,
    }
