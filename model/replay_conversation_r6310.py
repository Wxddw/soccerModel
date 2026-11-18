"""Read-only retrospective arithmetic on the November 13 chat recap, not model backtesting.
No imports from this module into the prematch prediction path.
"""
from __future__ import annotations

from shadow_r639 import _score

WDL = ('胜', '平', '负')
JC = ('让胜', '让平', '让负')


def _wdl(h: int, a: int) -> str:
    return '胜' if h > a else '平' if h == a else '负'


def audit_recap(data: dict) -> dict:
    if not isinstance(data, dict) or data.get('provenance') != 'PRIOR_CHAT_REFERENCE_NO_OFFICIAL_PREMATCH_FREEZE':
        raise ValueError('only explicitly labelled conversation recap may be audited')
    rows = data.get('matches')
    if not isinstance(rows, list) or len(rows) != 11:
        raise ValueError('expected the full 11-row chat recap')
    seen = set()
    output = []
    for x in rows:
        mid = x.get('id')
        if mid not in [f'{i:03}' for i in range(1,12)] or mid in seen:
            raise ValueError('duplicate or invalid match id')
        seen.add(mid)
        if x.get('snapshot_origin') not in ('AFTERNOON_PRIOR_TO_KICKOFF', 'LATE_NIGHT_PRIOR_TO_KICKOFF'):
            raise ValueError('each record needs its distinct prematch conversation origin')
        h, a = _score(x['actual_score'])
        ht, at = _score(x['actual_halftime'])
        full = _wdl(h,a)
        half_full = _wdl(ht,at) + full
        line = x['jc_line_as_reported_in_chat']
        if type(line) is not int or line < -3 or line > 3:
            raise ValueError('integer JC line from conversation required')
        jc = '让胜' if h+line > a else '让平' if h+line == a else '让负'
        single, pair = x['single'], x['protection']
        if single not in WDL or type(pair) is not list or len(pair) != 2 or len(set(pair)) != 2 or single not in pair or any(v not in WDL for v in pair):
            raise ValueError('invalid single/protection record')
        if x['jc_pick'] not in JC:
            raise ValueError('invalid JC pick')
        goals, scores, hf = x['goal_top3'], x['score_top3'], x['htft_top2']
        if not isinstance(goals,list) or len(goals)!=3 or len(set(goals))!=3 or any(type(g) is not int or g<0 for g in goals):
            raise ValueError('goal top3 requires three exact integer goals')
        if not isinstance(scores,list) or len(scores)!=3 or len(set(scores))!=3:
            raise ValueError('score Top3 invalid')
        for s in scores: _score(s)
        if not isinstance(hf,list) or len(hf)!=2 or len(set(hf))!=2 or any(len(v)!=2 or v[0] not in WDL or v[1] not in WDL for v in hf):
            raise ValueError('HT/FT Top2 invalid')
        output.append({
            'id':mid, 'actual_score':x['actual_score'], 'actual_wdl':full,
            'actual_jc':jc,'actual_goal':h+a,'actual_htft':half_full,
            'snapshot_origin':x['snapshot_origin'],
            'single_hit': single == full,
            'protection_hit': full in pair,
            'jc_hit': x['jc_pick'] == jc,
            'goal_top3_hit': h+a in goals,
            'score_top3_hit': x['actual_score'] in scores,
            'score_top1_hit': x['actual_score'] == scores[0],
            'htft_top2_hit': half_full in hf,
            'let_draw_in_frozen_choice': x['jc_pick'] == '让平',
        })
    output.sort(key=lambda r:r['id'])
    keys = ('single_hit','protection_hit','jc_hit','goal_top3_hit','score_top3_hit','score_top1_hit','htft_top2_hit')
    return {
        'status': 'PRIOR_CHAT_REFERENCE_NOT_OFFICIALLY_FROZEN_NOT_HOLDOUT',
        'date_of_sales': '2026-11-13',
        'production_score_eligible':False,
        'independent_validation':False,
        'training_or_calibration_performed':False,
        'metrics':{k:{'hits':sum(r[k] for r in output),'n':11} for k in keys},
        'actual_let_draw_matches':[r['id'] for r in output if r['actual_jc']=='让平'],
        'let_draw_predicted_count':sum(r['let_draw_in_frozen_choice'] for r in output),
        'different_snapshot_origin_001':True,
        'line_is_independently_official_verified':False,
        'rows':output,
        'notes':['001 afternoon pregame chat snapshot; 002-011 late night pregame chat snapshot.',
                 'The 11 results/lines are transcribed from the conversation recap and have not been separately sourced as a frozen official dataset.',
                 'The recap is forbidden as input for training, tuning thresholds or prematch inspect.'],
    }
