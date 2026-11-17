#!/usr/bin/env python3
"""Retrospective AUDIT of archived selections, never a R6.3.13 forward validation.

Uses the project's existing joint_bridge_r6312 mappings and
forward_validation_r6313._rps solely for POSTMATCH scoring. It never fits
lambdas, reconstructs score probabilities from picks, or edits Production.
"""
from __future__ import annotations
import csv,json,sys,math,collections,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0, str(root if (root/'joint_bridge_r6312.py').is_file() else root/'M79_Shadow_R6_3_13'))
import joint_bridge_r6312 as joint
import forward_validation_r6313 as fw
modelpath=root if (root/'joint_bridge_r6312.py').is_file() else root/'M79_Shadow_R6_3_13'

def load(file):return json.loads((modelpath/file).read_text(encoding='utf-8'))
def make_row(date, id, actual, *, match='', origin='', single=None, protect=None, score=None, goals=None,jc=None,line=None,half=None,half_picks=None,sale=None,wdl_is_inferred=False):
    return {'date':date,'id':id,'match':match,'actual_score':actual,'actual_halftime':half,
        'source_grade':origin,'single':single,'protection':protect or None,'score_top3':score or None,
        'goal_top3':goals or None,'jc_top1':jc,'official_line_as_archived':line,
        'half_full_top2':half_picks or None,'ordinary_sale':sale,'wdl_is_inferred_from_score_top1':wdl_is_inferred}

rows=[]
for r in load('RECAP_20261112_6_MATCHES_CONVERSATION_ONLY.json'):
 rows.append(make_row('2026-11-12',r['id'],r['actual_score'],match=r['match'],origin='prior_conversation_non_frozen',single=r['single'],protect=r['protection'],score=r['scores_top3'],goals=r['goals_top3'],jc=r['jc_pick'],line=r['official_handicap_line'],sale=r['ordinary_sale']))
for r in load('RECAP_20261113_11_MATCHES_CONVERSATION_ONLY.json')['matches']:
 rows.append(make_row('2026-11-13',r['id'],r['actual_score'],origin='prior_conversation_non_frozen',single=r['single'],protect=r['protection'],score=r['score_top3'],goals=r['goal_top3'],jc=r['jc_pick'],line=r['jc_line_as_reported_in_chat'],half=r['actual_halftime'],half_picks=r['htft_top2']))
for r in load('RECAP_20261114_14_MATCHES_CONVERSATION_ONLY_DEV.json')['matches']:
 top=r['pred_score_top3'][0]; h,a=joint.parse_score(top)
 rows.append(make_row('2026-11-14',r['id'],r['actual_score'],origin='odds_free_score_based_wdl_chat_dev',single=joint.wdl_label(h,a),score=r['pred_score_top3'],goals=r['pred_goal_top3'],wdl_is_inferred=True))
# Previously published pre-match 7-match predictions, explicitly not R6.3.13 predictions.
nov15=[
 ('005','马斯特里赫特—维迪斯','2:1','负',['平','负'],['1:2','1:1','0:1'],[3,2,4],1,'让胜',['平负','负负']),
 ('006','拉脱维亚—亚美尼亚','0:0','负',['平','负'],['0:1','1:1','0:0'],[2,1,3],1,'让胜',['平负','平平']),
 ('007','塞浦路斯—黑山','1:4','平',['平','负'],['1:1','1:2','0:1'],[2,3,1],1,'让胜',['平平','平负']),
 ('008','芬兰—圣马力诺','7:2','胜',['胜','平'],['3:0','4:0','2:0'],[3,4,5],-4,'让负',['胜胜','平胜']),
 ('009','克罗地亚—捷克','2:1','胜',['胜','平'],['2:0','2:1','1:0'],[2,3,1],-1,'让胜',['胜胜','平胜']),
 ('010','西班牙—英格兰','2:3','胜',['胜','平'],['2:1','1:1','2:0'],[3,2,4],-1,'让负',['平胜','胜胜']),
 ('011','比利时—意大利','4:1','胜',['胜','平'],['2:1','1:1','1:0'],[3,2,4],-1,'让负',['平胜','平平']),
]
for id,match,actual,single,prot,score,goals,line,jc,hts in nov15:
 rows.append(make_row('2026-11-15',id,actual,match=match,origin='chat_reconstruction_no_external_freeze',single=single,protect=prot,score=score,goals=goals,line=line,jc=jc,half_picks=hts))
nov16data=load('RECAP_DEV_20261116_CONVERSATION_ONLY_NOT_FORWARD_R6312.json')['matches']
nov16wdl={
'001':('胜',['胜','平'],['平平','平胜'],'1:0'),
'002':('负',['平','负'],['平负','平平'],'1:0'),
'003':('胜',['胜','平'],['平胜','平平'],'1:1'),
'004':('胜',['胜','平'],['胜胜','平胜'],'2:0'),
'005':('胜',['胜','平'],['平胜','平平'],'1:0'),
'006':('胜',['胜','平'],['平胜','胜胜'],'1:0'),
'007':('负',['平','负'],['平负','负负'],'0:1'),
'008':('胜',['胜','平'],['平胜','胜胜'],'0:0'),
}
for r in nov16data:
 s,p,hts,half=nov16wdl[r['id']]
 rows.append(make_row('2026-11-16',r['id'],r['actual_score'],match=r['home']+'—'+r['away'],origin='prior_chat_no_full_Q',single=s,protect=p,score=r['published_score_top3'],goals=r['published_goal_top3'],line=r['official_jc_home_line'],jc=r['published_frozen_jc'],half=half,half_picks=hts))
assert len(rows)==46

def eva(r):
    h,a=joint.parse_score(r['actual_score'])
    w=joint.wdl_label(h,a);total=h+a
    r['actual_wdl']=w;r['actual_goals']=total
    r['single_hit']=None if r['single'] is None else int(r['single']==w)
    r['protection_hit']=None if r['protection'] is None else int(w in r['protection'])
    r['score_top1_hit']=None if r['score_top3'] is None else int(r['score_top3'][0]==r['actual_score'])
    r['score_top3_hit']=None if r['score_top3'] is None else int(r['actual_score'] in r['score_top3'])
    r['goals_top3_hit']=None if r['goal_top3'] is None else int(str(total) in {str(x) for x in r['goal_top3']})
    if r['official_line_as_archived'] is not None:
      r['actual_jc']=joint.jc_label(h,a,r['official_line_as_archived'])
      r['jc_top1_hit']=int(r['actual_jc']==r['jc_top1']) if r['jc_top1'] else None
      s3=r['score_top3'] or []
      mapped=[joint.jc_label(*joint.parse_score(s),r['official_line_as_archived']) for s in s3]
      r['score_top3_letdraw_count']=mapped.count('让平')
      r['letdraw_two_candidates_but_jc_other']=int(mapped.count('让平')>=2 and r['jc_top1']!='让平')
    else:
      r['actual_jc']=None;r['jc_top1_hit']=None;r['score_top3_letdraw_count']=None;r['letdraw_two_candidates_but_jc_other']=None
    if r['score_top3'] is not None and r['goal_top3'] is not None:
      score_buckets={joint.goal_bucket(*joint.parse_score(x)) for x in r['score_top3']}
      goal_buckets={str(g) if str(g) in ['0','1','2','3','4','5','6'] else '7+' for g in r['goal_top3']}
      missing=sorted(goal_buckets-score_buckets)
      r['goal_top3_without_score_top3_representative_count']=len(missing)
      r['goal_top3_missing_bins']=';'.join(missing)
    else:
      r['goal_top3_without_score_top3_representative_count']=None
      r['goal_top3_missing_bins']=None
    if r['actual_halftime'] and r['half_full_top2']:
      h1,a1=joint.parse_score(r['actual_halftime'])
      actual_ht=joint.wdl_label(h1,a1)+w
      r['actual_htft']=actual_ht
      r['htft_top1_hit']=int(actual_ht==r['half_full_top2'][0])
      r['htft_top2_hit']=int(actual_ht in r['half_full_top2'])
    else:
      r['actual_htft']=None;r['htft_top1_hit']=None;r['htft_top2_hit']=None
    return r
rows=[eva(r) for r in rows]

metrics=['single_hit','protection_hit','jc_top1_hit','goals_top3_hit','score_top1_hit','score_top3_hit','htft_top1_hit','htft_top2_hit']
def summ(group):
 d={'n':len(group)}
 for k in metrics:
  vals=[x[k] for x in group if x[k] is not None]
  d[k]={'hits':sum(vals),'n':len(vals),'rate':sum(vals)/len(vals) if vals else None}
 d['actual_jc_letdraw_n']=sum(x['actual_jc']=='让平' for x in group)
 d['jc_top1_letdraw_n']=sum(x['jc_top1']=='让平' for x in group)
 d['score_top3_two_letdraw_not_first_n']=sum((x['letdraw_two_candidates_but_jc_other'] or 0) for x in group)
 d['matches_with_goal_score_coverage_gap']=sum((x['goal_top3_without_score_top3_representative_count'] or 0)>0 for x in group)
 d['goal_score_unrepresented_slots']=sum((x['goal_top3_without_score_top3_representative_count'] or 0) for x in group)
 return d
bydate={d:summ([r for r in rows if r['date']==d]) for d in sorted(set(x['date'] for x in rows))}
byday=list(bydate)
all_summary=summ(rows)

# Independent early 14 + 13 archive: can score actual WDL probabilities, but cannot derive R6.3.13 Q or issue forecasts.
other=[]
for source in ['RECAP_13_INPUT_CONVERSATION_ONLY.json','RECAP_14_INPUT_CONVERSATION_ONLY.json']:
 for x in load(source):
  p=x['probabilities'];pred=dict(zip(joint.WDL,map(float,p)))
  if 'actual' in x:actual=x['actual']
  else:actual=joint.wdl_label(*map(int,x['actual_score']))
  score_entry={"source":source,"match_id":x['id'],"actual_wdl":actual,"model_wdl":pred,
     "wdl_top1_hit":int(max(joint.WDL,key=lambda k:pred[k])==actual),
     "brier":sum((pred[k]-(1 if k==actual else 0))**2 for k in joint.WDL),
     "rps":fw._rps(pred,actual,joint.WDL),
     "log_loss":-math.log(pred[actual]) if pred[actual]>0 else None}
  other.append(score_entry)

other_stats={}
for source in sorted(set(x['source'] for x in other)):
 g=[x for x in other if x['source']==source]
 other_stats[source]={'n':len(g),'wdl_top1':sum(x['wdl_top1_hit'] for x in g),
  'brier':statistics.mean(x['brier'] for x in g),'rps':statistics.mean(x['rps'] for x in g),
  'log_loss':statistics.mean(x['log_loss'] for x in g)}

# Historic comparative parallel scheme on the same 14 (only direct chat report, not identical frozen input/time).
oddsaware_14=[
 ('003',['1:2','1:1','2:2'],[3,4,2]),('004',['1:0','2:0','2:1'],[2,3,1]),('005',['2:1','2:0','3:1'],[3,4,2]),
 ('006',['1:1','0:1','1:0'],[2,3,1]),('007',['2:1','2:0','3:0'],[3,4,2]),('008',['2:1','1:1','1:2'],[3,4,2]),
 ('009',['2:1','1:1','3:1'],[3,4,5]),('010',['2:1','3:1','2:0'],[3,4,2]),('011',['2:1','1:0','2:0'],[2,3,1]),
 ('012',['2:0','2:1','1:0'],[3,2,4]),('013',['1:2','1:1','0:1'],[3,2,4]),('014',['2:1','2:0','3:1'],[3,4,2]),
 ('015',['1:1','2:1','1:0'],[2,3,1]),('016',['0:2','1:2','0:1'],[3,2,4]),
]
nov14={r['id']:r for r in rows if r['date']=='2026-11-14'}
oddsaware=[]
for id,scores,goals in oddsaware_14:
 a=nov14[id]['actual_score'];h,g=joint.parse_score(a);bh,bg=joint.parse_score(scores[0]);w=joint.wdl_label(h,g)
 oddsaware.append({'id':id,'actual_score':a,'single_score_derived_hit':int(joint.wdl_label(bh,bg)==w),
  'score_top1_hit':int(a==scores[0]),'score_top3_hit':int(a in scores),'goal_top3_hit':int(h+g in goals)})

out={'description':'Research diagnostics only: not R6.3.13 historical forecasts or live forward test',
 'project_model':'M79.3.6 Production FROZEN + Shadow R6.3.13',
 'data_grading':'Prior conversation selections, retrospective outcomes; no independent immutable pre-match probability grid Q for any of 46',
 'n':len(rows),'dates':bydate,'pooled_DESCRIPTIVE_ONLY':all_summary,
 'early_archive_probabilities_development_only':other_stats,
 'nov14_odds_aware_same_games_DIFFERENT_INPUT_TIME':{
  'n':len(oddsaware),'single_score_derived_hits':sum(x['single_score_derived_hit'] for x in oddsaware),
  'score_top1_hits':sum(x['score_top1_hit'] for x in oddsaware),
  'score_top3_hits':sum(x['score_top3_hit'] for x in oddsaware),
  'goal_top3_hits':sum(x['goal_top3_hit'] for x in oddsaware)},
 'excluded_11_15_finished_before_forecast':4,
 'not_available':['Prematch complete Q','Historical estimated home/away lambdas','prematch market timestamped odds for 46','historical fit parameters for halftime','independent immutable time proof'],
 'R6313_verified_accuracy':None,'R6313_full_matrix_scoreable_n':0,'R6313_forward_certified_n':0,
 'no_training_or_parameter_tuning':True}

(root/'HISTORIC_AUDIT_20261117_R6313_DEV.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'HISTORIC_AUDIT_46_MATCH_DETAILS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'EARLY_27_MATCH_PROPER_SCORES_DEV.json').write_text(json.dumps(other,ensure_ascii=False,indent=2),encoding='utf-8')
flat=[]
for r in rows:
 v={k:(';'.join(str(i) for i in val) if isinstance(val,list) else val) for k,val in r.items()}
 flat.append(v)
with (root/'HISTORIC_AUDIT_46_MATCH_DETAILS.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0].keys()));w.writeheader();w.writerows(flat)
print(json.dumps({'dates':bydate,'pooled':all_summary,'early':other_stats,'nov14oddsaware':out['nov14_odds_aware_same_games_DIFFERENT_INPUT_TIME']},ensure_ascii=False,indent=2))
