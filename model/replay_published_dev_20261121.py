"""Score *published* 11/20 eight-game qualitative predictions, postmatch ONLY.
Not six-period HTFT/Q performance. Never feeds outcomes into prematch models.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path
from matchday_publish_gate_r636 import published_only_bias


def _wdl(a, b):
    return '胜' if a > b else '平' if a == b else '负'


def replay(doc):
    if doc.get('status') != 'DEVELOPMENT_ONLY_NOT_INDEPENDENT_PREMATCH_Q':
        raise ValueError('retrospective development-only source required')
    rows = doc['rows']
    publication = []
    stats = Counter()
    per_game = []
    for row in rows:
        h, a = (int(x) for x in row['actual'].split(':'))
        hh, ha = (int(x) for x in row['half'].split(':'))
        if hh > h or ha > a: raise ValueError('impossible HT/FT')
        actual_wdl = _wdl(h, a)
        actual_jc = '让胜' if h + row['official_jc_line'] > a else '让平' if h + row['official_jc_line'] == a else '让负'
        htft = _wdl(hh, ha) + actual_wdl
        out = dict(id=row['id'],goal_top3=int(h+a in row['goal_top3']),
                   goal_top2=int(h+a in row['goal_top2']),
                   score_top3=int(row['actual'] in row['score_top3']),
                   jc=int(row['jc_pick']==actual_jc),
                   htft_main=int(row['htft_main']==htft),
                   htft_top2=int(htft in (row['htft_main'],row['htft_backup'])))
        if row['ordinary_offered']:
            stats['ordinary_n'] += 1
            out['wdl_single'] = int(row['frozen_wdl']==actual_wdl)
            out['wdl_protection'] = int(actual_wdl in row['wdl_protection'])
            stats['wdl_single'] += out['wdl_single']
            stats['wdl_protection'] += out['wdl_protection']
        for k in ('goal_top3','goal_top2','score_top3','jc','htft_main','htft_top2'):
            stats[k] += out[k]
        publication.append({'match_id':row['id'],'ordinary_offered':row['ordinary_offered'],
                            'frozen_wdl':row['frozen_wdl'],'htft_primary':row['htft_main']})
        per_game.append(out)
    return dict(status='POSTMATCH_DEVELOPMENT_ONLY',n=len(rows),stats=dict(stats),
                concentration=published_only_bias(publication),details=per_game,
                comparable_new_model_probabilities=False,formal_grant=None)


if __name__ == '__main__':
    src=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('DEV_ONLY_CASEBOOK_20261120_8.json')
    obj=replay(json.loads(src.read_text(encoding='utf-8')))
    print(json.dumps(obj,ensure_ascii=False,indent=2))
