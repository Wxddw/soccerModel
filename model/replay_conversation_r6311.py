"""Development-only recap arithmetic; never imported into prematch inspect."""
from __future__ import annotations
from collections import Counter


def audit_dev14(data):
    if not isinstance(data,dict) or data.get('grade')!='CONVERSATION_ONLY_DEV_NEVER_FORWARD' or not isinstance(data.get('matches'),list):
        raise ValueError('development recap requires explicit grade and matches')
    matches=data['matches'];ids=[];counts=Counter()
    for row in matches:
        if set(row)!={'id','pred_score_top3','pred_goal_top3','actual_score'}:raise ValueError('recap row shape')
        if not isinstance(row['id'],str) or not row['id'].strip():raise ValueError('id invalid')
        ids.append(row['id'])
        preds=row['pred_score_top3']; gpred=row['pred_goal_top3']
        if not isinstance(preds,list) or len(preds)!=3 or len(set(preds))!=3 or not isinstance(gpred,list) or len(gpred)!=3 or len(set(gpred))!=3:raise ValueError('recap Top3 invalid')
        h,a=map(int,row['actual_score'].split(':'))
        ph,pa=map(int,preds[0].split(':'))
        ac='胜' if h>a else '平' if h==a else '负'
        pd='胜' if ph>pa else '平' if ph==pa else '负'
        counts['wdl_hit']+=ac==pd
        counts['score_top1_hit']+=row['actual_score']==preds[0]
        counts['score_top3_hit']+=row['actual_score'] in preds
        counts['goal_top3_hit']+=(h+a) in gpred
    if len(ids)!=len(set(ids)):raise ValueError('duplicate match id')
    return {'n':len(matches),'metrics':{key:{'hits':counts[key],'n':len(matches)} for key in ('wdl_hit','score_top1_hit','score_top3_hit','goal_top3_hit')},
            'source_grade':'CONVERSATION_ONLY_DEV_NEVER_FORWARD',
            'eligible_for_training':False,'eligible_for_independent_validation':False,
            'production_predictions_replayed':False,'thresholds_fit_from_outcomes':False}
