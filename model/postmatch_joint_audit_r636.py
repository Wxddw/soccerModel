"""R6.3.6 postmatch research: additive read-only exact-margin/score matrix audit.

Does not grant selections, modify Production, infer official JC lines, or use results.
Independent of historical shadow_r636.py. Python 3.10+ standard library.
"""
from collections import defaultdict
from math import isfinite


def audit_joint_q(rows, official_jc_line=None, tolerance=1e-8):
    """Return exact exhaustive margins, 0..6/7+ goal bins, WDL and official JC triad.

    rows: FULL prematch [{'score':'H:A','probability':float}, ...].
    Returns probabilities but NEVER a formal wagering direction.
    A score grid truncated without remaining tail mass is not normalized and is rejected.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError("full score matrix required")
    if official_jc_line is not None and (
        isinstance(official_jc_line, bool) or
        not isinstance(official_jc_line, int) or
        official_jc_line not in (-3, -2, -1, 0, 1, 2, 3)
    ):
        raise ValueError("JC line must be official signed INTEGER -3..+3; not Asian line")
    grid = {}
    total = 0.0
    for row in rows:
        if not isinstance(row, dict) or set(("score", "probability")) - set(row):
            raise ValueError("each row requires score and probability")
        score = row["score"]
        try:
            ss = score.split(":")
            if len(ss) != 2 or any(not s.isdigit() for s in ss):
                raise ValueError()
            h, a = (int(s) for s in ss)
            p = float(row["probability"])
        except (ValueError, TypeError, AttributeError):
            raise ValueError("invalid score/probability") from None
        if (h, a) in grid:
            raise ValueError("duplicate score cell")
        if not isfinite(p) or p < 0 or p > 1:
            raise ValueError("invalid cell probability")
        grid[h, a] = p
        total += p
    if abs(total - 1.0) > tolerance:
        raise ValueError("unaccounted score probability mass; do not renormalize")
    wdl = {"胜": 0., "平": 0., "负": 0.}
    jc = {"让胜": 0., "让平": 0., "让负": 0.} if official_jc_line is not None else None
    margins = defaultdict(float)
    goals = {str(i): 0. for i in range(7)}
    goals["7+"] = 0.
    for (h, a), p in grid.items():
        margin = h - a
        margins[margin] += p
        wdl["胜" if margin > 0 else "平" if margin == 0 else "负"] += p
        goals[str(h+a) if h+a <= 6 else "7+"] += p
        if jc is not None:
            diff = margin + official_jc_line
            jc["让胜" if diff > 0 else "让平" if diff == 0 else "让负"] += p
    ranked_scores = sorted(grid.items(), key=lambda x: (-x[1], x[0]))
    ranked_goals = sorted(goals, key=lambda k: (-goals[k], int(k.rstrip("+"))))
    top3 = [(f"{h}:{a}", p) for (h, a), p in ranked_scores[:3]]
    represented_goals = {str(h+a) if h+a <= 6 else "7+" for (h, a), _ in ranked_scores[:3]}
    return {
        "research_only": True,
        "formal_grant": None,
        "input_mass": total,
        "wdl": wdl,
        "exact_margin": dict(sorted(margins.items())),
        "margin_buckets": {
            "away_3plus": sum(p for d,p in margins.items() if d <= -3),
            "away_2": margins[-2], "away_1": margins[-1], "draw": margins[0],
            "home_1": margins[1], "home_2": margins[2],
            "home_3plus": sum(p for d,p in margins.items() if d >= 3),
        },
        "goals": goals,
        "score_top3": top3,
        "goal_top3": ranked_goals[:3],
        "goal_top3_unrepresented_by_score_top3": [k for k in ranked_goals[:3] if k not in represented_goals],
        "official_jc_integer_line": official_jc_line,
        "jc": jc,
        "jc_exact_draw_margin": -official_jc_line if official_jc_line is not None else None,
        "jc_top2_near_tie_5pp": (
            sorted(jc.values(), reverse=True)[0]-sorted(jc.values(), reverse=True)[1] <= .05
            if jc is not None else None
        ),
    }
