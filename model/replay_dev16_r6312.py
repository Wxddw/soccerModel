"""Offline chat-level diagnosis only. NEVER imported into prematch model.

No fake historical score probabilities, no training, no accuracy promotion.
"""
import json
from pathlib import Path
from joint_bridge_r6312 import parse_score,jc_label,goal_bucket


def audit(rows:list[dict])->dict:
    out=[]
    for r in rows:
        line=r['official_jc_home_line']
        published=r['published_score_top3'];g=r['published_goal_top3']
        mapped=[]
        for score in published:
            h,a=parse_score(score)
            mapped.append({'score':score,'goal_bucket':goal_bucket(h,a),
                           'jc':jc_label(h,a,line)})
        absent=[k for k in g if k not in [v['goal_bucket'] for v in mapped]]
        acth,acta=parse_score(r['actual_score'])
        actual_jc=jc_label(acth,acta,line)
        out.append({'match_id':r['id'],'score_top3_mapping':mapped,
                    'goal_top3_absent_from_score_top3':absent,
                    'score_top3_letdraw_count':sum(m['jc']=='让平' for m in mapped),
                    'actual_jc':actual_jc,'frozen_jc':r['published_frozen_jc'],
                    'frozen_jc_hit':r['published_frozen_jc']==actual_jc,
                    'historical_chat_only_no_probability_matrix':True})
    return {'period':'2026-11-16','grade':'CONVERSATION_ONLY_DEV_NOT_FORWARD',
            'n':len(rows),'actual_letdraw_count':sum(x['actual_jc']=='让平' for x in out),
            'published_jc_top1_hits':sum(x['frozen_jc_hit'] for x in out),
            'missing_goal_family_matches':sum(bool(x['goal_top3_absent_from_score_top3']) for x in out),
            'multiple_scoretop3_letdraw_but_frozen_not_letdraw_count':sum(
                x['score_top3_letdraw_count']>=2 and x['frozen_jc']!='让平' for x in out),
            'matches':out, 'auto_updated_or_refitted':False}


if __name__=='__main__':
    folder=Path(__file__).parent
    rows=json.loads((folder/'RECAP_DEV_20261116_CONVERSATION_ONLY_NOT_FORWARD_R6312.json').read_text(encoding='utf-8'))['matches']
    result=audit(rows)
    path=folder/'RECAP_DEV16_AUDIT_R6312.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Development-only diagnostics', {k:result[k] for k in ('n','actual_letdraw_count','published_jc_top1_hits','missing_goal_family_matches','multiple_scoretop3_letdraw_but_frozen_not_letdraw_count')})
