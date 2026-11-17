"""Research-only historical ablation across five European leagues (2025/2026).

No M79 Production weights or forecasts are used. Public-domain score data:
https://github.com/openfootball/football.json

Use: python historical_context_ablation_r6315.py --data-dir /path/to/json
Needs season/league files (2024-25, 2025-26, 2026-27; en.1, de.1,
es.1, it.1, fr.1). Optional --download downloads into the chosen data dir.
Only recorded actual fulltime scores are included. Prediction features are built
from games dated strictly earlier than their kickoff date; no same-day labels.
"""
from __future__ import annotations
import argparse, collections, datetime, json, math, random, statistics, urllib.request
from pathlib import Path

LEAGUES=('en.1','de.1','es.1','it.1','fr.1')
SEASONS=('2024-25','2025-26','2026-27')
END=datetime.date(2026,11,16)
URL='https://raw.githubusercontent.com/openfootball/football.json/master/'
FEATURES=('form','rest','congestion','homeadv')
COEFFICIENTS=(-.30,-.20,-.12,-.08,-.04,0.,.04,.08,.12,.20,.30)

def clamp(x,lo,hi):return max(lo,min(hi,x))

def load_matches(data_dir:Path,download:bool=False):
    results=[];sources=[]
    for season in SEASONS:
      for lg in LEAGUES:
        filename=data_dir/season/(lg+'.json')
        if download:
            filename.parent.mkdir(parents=True,exist_ok=True)
            urllib.request.urlretrieve(URL+season+'/'+lg+'.json',filename)
        if not filename.exists():raise FileNotFoundError(filename)
        doc=json.loads(filename.read_text('utf8'));n=0
        for match in doc['matches']:
            sc=match.get('score',{})
            if isinstance(sc,dict):sc=sc.get('ft')
            if not isinstance(sc,list) or len(sc)!=2 or any(type(v) is not int for v in sc):continue
            try:date=datetime.date.fromisoformat(match['date'])
            except (ValueError,KeyError):continue
            if date>END:continue
            results.append({'date':date,'league':lg,'h':match['team1'],'a':match['team2'],
                            'gh':sc[0],'ga':sc[1]})
            n+=1
        sources.append({'source':season+'/'+lg+'.json','n':n})
    return sorted(results,key=lambda r:(r['date'],r['league'],r['h'],r['a'])),sources

def features_for(row,history,lastday,teamgames):
    lg=row['league'];home=row['h'];away=row['a'];previous=history[lg]
    scores=previous[-400:]
    league_home=(sum(r['gh'] for r in scores)+1.5*70)/(len(scores)+70)
    league_away=(sum(r['ga'] for r in scores)+1.2*70)/(len(scores)+70)
    def team_records(team):
        g=[r for r in previous if team in (r['h'],r['a'])];z=[]
        for r in g:
            flag=r['h']==team;own=r['gh'] if flag else r['ga'];opp=r['ga'] if flag else r['gh']
            z.append((own,opp,3 if own>opp else 1 if own==opp else 0))
        return z
    H=team_records(home);A=team_records(away)
    def rate(v,idx,mu):
        v=v[-16:];return (sum(x[idx] for x in v)+8*mu)/(len(v)+8)
    hl=rate(H,0,(league_home+league_away)/2);hc=rate(H,1,(league_home+league_away)/2)
    al=rate(A,0,(league_home+league_away)/2);ac=rate(A,1,(league_home+league_away)/2)
    mh=clamp(hl*ac/1.3*league_home/1.5,.15,4.5)
    ma=clamp(al*hc/1.3*league_away/1.2,.15,4.5)
    def ppg(v):
        v=v[-5:];return (sum(x[2] for x in v)+3*2.8)/(len(v)+3)
    form=clamp((ppg(H)-ppg(A))/3,-1,1)
    rh=(row['date']-lastday[lg][home]).days if home in lastday[lg] else 7
    ra=(row['date']-lastday[lg][away]).days if away in lastday[lg] else 7
    rest=clamp((rh-ra)/7.,-1,1)
    bh=sum(1 for day in teamgames[lg][home] if 0<(row['date']-day).days<=14)
    ba=sum(1 for day in teamgames[lg][away] if 0<(row['date']-day).days<=14)
    congestion=clamp((ba-bh)/2.,-1,1)
    hh=[r for r in previous if r['h']==home][-8:]
    h_away=[r for r in previous if r['a']==home][-8:]
    homeadv=clamp(((sum(r['gh']-r['ga'] for r in hh)+2)/(len(hh)+4))-
                  ((sum(r['ga']-r['gh'] for r in h_away)+2)/(len(h_away)+4)),-2,2)/2
    return {'mh':mh,'ma':ma,'form':form,'rest':rest,'congestion':congestion,'homeadv':homeadv}

def prepare(matches):
    hist=collections.defaultdict(list)
    lastday=collections.defaultdict(dict)
    games=collections.defaultdict(lambda:collections.defaultdict(list))
    finished=[];pending=[];current=None
    def flush():
        for r in pending:
            hist[r['league']].append(r);lastday[r['league']][r['h']]=r['date'];lastday[r['league']][r['a']]=r['date']
            games[r['league']][r['h']].append(r['date']);games[r['league']][r['a']].append(r['date'])
    for source in matches:
        if source['date']!=current:flush();pending=[];current=source['date']
        r=source.copy();r.update(features_for(r,hist,lastday,games));finished.append(r);pending.append(r)
    flush();return finished

def lams(r,coeff):
    z=sum(coeff[k]*r[k] for k in coeff)
    return clamp(r['mh']*math.exp(z),.1,6.),clamp(r['ma']*math.exp(-z),.1,6.)

def probs(lh,la):
    ph=[math.exp(-lh)];pa=[math.exp(-la)]
    for i in range(1,12):ph.append(ph[-1]*lh/i);pa.append(pa[-1]*la/i)
    p=[0.,0.,0.]
    for i,hi in enumerate(ph):
        for j,aj in enumerate(pa):p[0 if i>j else 1 if i==j else 2]+=hi*aj
    s=sum(p);return [v/s for v in p]

def losses(r,coeff):
    lh,la=lams(r,coeff);p=probs(lh,la)
    y=0 if r['gh']>r['ga'] else 1 if r['gh']==r['ga'] else 2
    return {'ll':-math.log(max(1e-15,p[y])),
            'brier':sum((v-(k==y))**2 for k,v in enumerate(p)),
            'top1':int(max(range(3),key=lambda k:p[k])==y),
            'score_nll':lh-r['gh']*math.log(lh)+math.lgamma(r['gh']+1)+
                       la-r['ga']*math.log(la)+math.lgamma(r['ga']+1)}

def summary(rows,c):
    z=[losses(r,c) for r in rows]
    return {'n':len(z),'wdl_logloss':round(statistics.mean(v['ll'] for v in z),6),
            'wdl_brier':round(statistics.mean(v['brier'] for v in z),6),
            'top1':str(sum(v['top1'] for v in z))+'/'+str(len(z)),
            'score_nll':round(statistics.mean(v['score_nll'] for v in z),6)}

def fit(train):
    def poisson_loss(c):
        return statistics.mean(sum(lh-gh*math.log(lh) for lh,gh in [(lams(r,c)[0],r['gh']),
                                                                     (lams(r,c)[1],r['ga'])]) for r in train)
    single={k:min(COEFFICIENTS,key=lambda c:poisson_loss({k:c})) for k in FEATURES}
    multi=single.copy()
    for _ in range(3):
        for k in FEATURES:
            multi[k]=min(COEFFICIENTS,key=lambda c:poisson_loss({**multi,k:c}))
    return single,multi

def experiment(matches,sources,bootstrap_n=1000):
    rows=prepare(matches)
    train=[r for r in rows if datetime.date(2025,1,1)<=r['date']<=datetime.date(2025,12,31)]
    test=[r for r in rows if datetime.date(2026,1,1)<=r['date']<=END]
    if not train or not test:raise ValueError('Need disjoint 2025 and 2026 samples')
    single,multi=fit(train)
    opts={k:{k:v} for k,v in single.items()};opts['all']=multi
    results={}
    rng=random.Random(20261117)
    for k,c in opts.items():
        diffs=[losses(r,{})['ll']-losses(r,c)['ll'] for r in test]
        boots=sorted(sum(diffs[rng.randrange(len(diffs))] for _ in diffs)/len(diffs)
                     for _ in range(bootstrap_n))
        results[k]={'metrics':summary(test,c),'delta_ll':round(statistics.mean(diffs),6),
                    'iid_bootstrap95':[round(boots[int(.025*bootstrap_n)],6),
                                       round(boots[min(bootstrap_n-1,int(.975*bootstrap_n))],6)],
                    'by_league':{lg:round(statistics.mean(d for d,r in zip(diffs,test) if r['league']==lg),6)
                                 for lg in LEAGUES}}
    return {'source':'openfootball/football.json','sources':sources,'total_matches':len(matches),
            'train_n':len(train),'test_n':len(test),
            'test_max_date':str(max(r['date'] for r in test)),
            'selected_coefficients':single,'all_coefficients':multi,
            'train_baseline':summary(train,{}),'test_baseline':summary(test,{}),
            'candidate_results':results,'research_only':True,
            'limits':'Only five leagues; no injuries, tactics, cup matches, European travel, weather or coach labels; not M79 forecasts.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,required=True)
    ap.add_argument('--download',action='store_true');ap.add_argument('--output',type=Path)
    opts=ap.parse_args();matches,sources=load_matches(opts.data_dir,opts.download)
    report=experiment(matches,sources)
    body=json.dumps(report,ensure_ascii=False,indent=2)
    if opts.output:opts.output.write_text(body,encoding='utf8')
    print(body)
if __name__=='__main__':main()
