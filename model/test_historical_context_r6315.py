import datetime,math
from historical_context_ablation_r6315 import prepare,probs,losses,experiment,END

def row(d,h,a,gh,ga):
 return {'date':datetime.date.fromisoformat(d),'league':'en.1','h':h,'a':a,'gh':gh,'ga':ga}

def test_probs_total():
 assert abs(sum(probs(1.7,1.3))-1)<1e-12

def test_proper_score():
 r={'mh':1.4,'ma':1.0,'gh':1,'ga':0,'form':0,'rest':0,'homeadv':0,'congestion':0}
 out=losses(r,{})
 assert all(math.isfinite(out[k]) for k in ('ll','brier','score_nll'))

def test_same_date_not_leaked():
 rs=[row('2025-01-03','A','B',9,0),row('2025-01-03','B','C',0,9)]
 a=prepare(rs)
 rs2=[rs[1],rs[0]];b=prepare(rs2)
 z1={(r['h'],r['a']):(r['mh'],r['ma']) for r in a}
 z2={(r['h'],r['a']):(r['mh'],r['ma']) for r in b}
 assert z1==z2

def test_congestion_no_see_future():
 rs=[row('2025-01-01','A','B',3,0),row('2025-01-07','A','C',1,0),row('2025-01-09','B','C',1,0)]
 f=prepare(rs)
 assert f[0]['congestion']==0
 assert f[1]['congestion']<0

def test_cutoff_has_fixed_date():
 assert END == datetime.date(2026,11,16)
