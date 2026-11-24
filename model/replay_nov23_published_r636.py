"""Development-only replay of the Nov23 published text table, not a frozen-Q replay.
Actual results from cpbao BQQ/SPF/JQS record. No odds-path inference, no fitted weights.
Static odds are exactly the contemporaneous quoted prices in the conversation, but
lack independently verified per-price observation timestamps; they are proxies only.
"""
from collections import Counter
from selection_risk_r636_20261124 import normalized
import json
from pathlib import Path
ROWS=[
# id, line, regular pair, JC pair, goals, scores, HTFT, HT, FT, WDL odds, JC odds, goal odds, EU odds, AH home, crowd
('001',1,'负平','胜平',[3,2,4],['1:2','1:1','0:1'],['负负','平负'],(2,1),(3,2),[3.63,3.50,1.73],[1.80,3.27,3.60],[14,5.75,3.25,3.10,5.20,10,19,30],[3.19,3.49,2.08],.25,[.24,.26,.50]),
('002',-2,None,'胜负',[3,4,2],['3:0','2:0','3:1'],['胜胜','平胜'],(1,0),(3,1),None,[2.25,3.80,2.32],[29,8.60,4.95,3.40,3.95,6.10,10,11],[1.23,6.25,10.62],-2,None),
('003',1,'负胜','胜负',[3,4,2],['1:2','1:1','0:1'],['负负','平负'],(1,0),(3,0),[3.88,3.95,1.59],[1.98,3.20,3.12],[20,7.20,4.30,3.10,4.10,7.50,13.50,17],[3.52,3.77,1.95],.5,[.20,.22,.58]),
('004',-1,'胜平','负平',[2,3,1],['1:1','2:1','1:0'],['胜胜','平平'],(1,1),(2,3),[2.30,2.77,2.91],[5.25,3.85,1.45],[10.50,4.85,3.20,3.40,5.70,11,20,33],[2.32,3.27,2.86],-.25,[.32,.39,.29]),
('005',-1,'胜负','负平',[3,2,4],['1:1','2:1','1:2'],['胜胜','负负'],(2,0),(4,0),[2.18,3.15,2.75],[4.68,4.00,1.48],[14,5.80,3.45,3.15,5.15,8.80,17.50,26],[2.23,3.48,3.10],-.25,[.32,.34,.34]),
('006',-1,'胜负','负平',[3,2,4],['2:1','1:1','1:0'],['胜胜','平胜'],(0,0),(1,1),[1.73,3.63,3.50],[3.75,3.15,1.80],[15,6.40,4.00,3.15,4.20,8.25,16,24],[2.18,3.55,3.11],-.25,[.54,.31,.15]),
('007',-1,'胜平','负平',[2,3,1],['1:1','2:1','1:0'],['胜胜','平平'],(0,1),(1,1),[2.01,2.88,3.40],[4.63,3.35,1.60],[12,4.75,3.20,3.25,5.85,10,23,38],[2.28,3.32,2.98],-.25,[.43,.41,.16]),
('008',-1,'胜负','负平',[3,2,4],['1:1','2:1','1:2'],['胜胜','负负'],(1,0),(3,2),[2.25,3.18,2.63],[4.95,4.05,1.45],[15,6.60,3.75,3.20,4.40,8.20,15.50,23],[2.36,3.53,2.68],-.25,[.40,.34,.26])]
def wdl(d):return '胜' if d>0 else '平' if d==0 else '负'
def run():
    stats=Counter();den=Counter(); rows=[];exp5=0;exp_letdraw=0;exp_draw=0
    for i,line,pair,jpair,gs,ss,hs,ht,ft,wo,jo,go,eo,ah,crowd in ROWS:
        d=ft[0]-ft[1]; f=wdl(d); j=wdl(d+line); t=sum(ft); h=wdl(ht[0]-ht[1])+f
        hits={'wdl_single':None if pair is None else f==pair[0],'wdl_pair':None if pair is None else f in pair,'jc_single':j==jpair[0],'jc_pair':j in jpair,'goal_top3':t in gs,'goal_double':t in gs[:2],'score_top3':f'{ft[0]}:{ft[1]}' in ss,'htft_single':h==hs[0],'htft_pair':h in hs}
        for k,v in hits.items():
            if v is not None:den[k]+=1;stats[k]+=int(v)
        jp=normalized(jo);gp=normalized(go);exp5+=sum(gp[5:]);exp_letdraw+=jp[1]; wp=None if wo is None else normalized(wo); ep=normalized(eo)
        proxy={'jc_probabilities':jp,'goals_probabilities':gp,'goal_5plus':sum(gp[5:]),'letdraw_prob':jp[1],'jc_top2_gap':sorted(jp,reverse=True)[0]-sorted(jp,reverse=True)[1], 'draw_market_excess':None,'jc_eu_favorite_diff':None,'wdl_second_third_gap':None,'high_best_vs_third_gap':gp[gs[-1]]-max(gp[5:])}
        if wp is not None:
            exp_draw+=wp[1]; fav=max((0,2),key=lambda k:wp[k]);proxy.update({'wdl_probabilities':wp,'jc_eu_favorite_diff':wp[fav]-ep[fav],'wdl_second_third_gap':sorted(wp,reverse=True)[1]-sorted(wp,reverse=True)[2],'draw_market_excess':crowd[1]-wp[1] if crowd else None})
        rows.append({'match_id':i,'line':line,'regular_pair':pair,'jc_pair':jpair,'goals':gs,'scores':ss,'htft':hs,'ht':ht,'ft':ft,'actual_wdl':f,'actual_jc':j,'actual_htft':h,'hits':hits,'market_proxy_only':proxy,'raw_quoted_odds':{'regular':wo,'jc':jo,'goals':go,'euro_average':eo,'asian_home':ah,'buy_share':crowd}})
    return {'scope':'2026-11-23 eight published text picks, development only','complete_frozen_q_available':False,'per_quote_timestamp_verified':False,'can_score_full_model_logloss':False,'can_certify_market_signals':False,'hits':{k:{'hit':stats[k],'n':den[k]} for k in den},'goals_actual':dict(Counter(sum(r[8]) for r in ROWS)),'raw_odds_proxy_expected':{'5plus':exp5,'letdraw':exp_letdraw,'draw_regular_open':exp_draw},'actual':{'5plus':sum(sum(r[8])>=5 for r in ROWS),'letdraw':sum(wdl(r[8][0]-r[8][1]+r[1])=='平' for r in ROWS),'draw_regular_open':sum(r[2] is not None and r[8][0]==r[8][1] for r in ROWS)},'rows':rows}
if __name__=='__main__':
    import sys
    result=run();Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2))