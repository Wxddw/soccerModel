"""R6.3.6 read-only prematch suspicious-price/cold-price screening (SHADOW).

Never infer bookmaker *intent* from quoted prices. No outcome picks, probabilities,
production weights, confidence grades, or staking levels are modified.

Input packets contain bookmaker-specific *timestamped observed* odds, rather
than claiming a displayed 'initial' price is independently time-attested.
The whole 1X2/Asian/O-U odds ecosystem is ONE market evidence family.

Asian lines are the HOME handicap, e.g. -0.5 home gives half a goal, +0.5
home receives half a goal. Quarter-lines accepted here but never confused
with China's JC signed INTEGER handicap (a distinct three-way market).
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from collections import defaultdict
import json
import math
from statistics import median

VERSION = "R636_20261123_MARKET_TRAP_COLD_WATCH_SHADOW"
MARKETS = {"1x2", "asian", "ou"}
NONMARKET = {"roster", "tactics", "schedule", "weather", "motivation"}
SIDES = ("home", "away")


def _time(v):
    if not isinstance(v, str):
        raise ValueError("timezone-aware observed_at required")
    try:
        dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
    except ValueError as e:
        raise ValueError("invalid ISO time") from e
    if dt.utcoffset() is None:
        raise ValueError("naive times prohibited")
    return dt.astimezone(timezone.utc)


def _num(x, low, high):
    if type(x) not in (float, int) or not math.isfinite(x) or not low <= x <= high:
        raise ValueError("nonfinite/out of bounds number")
    return float(x)


def _implied(odds):
    w = [1.0/x for x in odds]
    z = math.fsum(w)
    if not .85 <= z <= 1.55:
        raise ValueError("implausible bookmaker overround")
    return [v/z for v in w], z


def _snapshot(row, cutoff, kickoff):
    required = {"bookmaker", "market", "observed_at", "source_url", "odds", "line_home", "line_goals"}
    if not isinstance(row,dict) or set(row) != required:
        raise ValueError("exact quote record required; no postmatch fields")
    book, market, url = row["bookmaker"], row["market"], row["source_url"]
    if not all(isinstance(x,str) and x.strip() for x in (book,url)) or not url.startswith("https://"):
        raise ValueError("valid book and source URL required")
    if market not in MARKETS:
        raise ValueError("invalid market")
    dt = _time(row["observed_at"])
    if dt > cutoff or dt >= kickoff:
        raise ValueError("postcutoff/postkickoff quote is prohibited")
    odds = row["odds"]
    if not isinstance(odds,list) or len(odds)!=(3 if market=="1x2" else 2):
        raise ValueError("market-specific odds count invalid")
    odds = [_num(o,1.01,1001.0) for o in odds]
    ps, margin = _implied(odds)
    ah, ou = row["line_home"],row["line_goals"]
    if market=="asian":
        ah=_num(ah,-7.,7.)
        if abs(4*ah-round(4*ah))>1e-8 or ou is not None:
            raise ValueError("quarter Asian handicap required")
    elif market=="ou":
        ou=_num(ou,.25,12.)
        if abs(4*ou-round(4*ou))>1e-8 or ah is not None:
            raise ValueError("quarter total-goals line required")
    elif ah is not None or ou is not None:
        raise ValueError("no line in 1x2 quotes")
    return {"bookmaker":book.strip(),"market":market,"at":dt,"source_url":url,
            "odds":odds,"probabilities":ps,"overround":margin,"line_home":ah,"line_goals":ou}


def _median_z(rows, idx):
    return median([q["probabilities"][idx] for q in rows])


def screen(packet):
    """Produce only prematch *review* flags, no odds-dependent candidate flip."""
    required={"match_id","cutoff","kickoff","official_jc_signed_line","quotes",
              "crowd","independent_evidence"}
    if not isinstance(packet,dict) or set(packet)!=required:
        raise ValueError("strict prematch schema, result/score fields are prohibited")
    match_id = packet["match_id"]
    if not isinstance(match_id,str) or not match_id.strip():
        raise ValueError("match_id missing")
    cutoff,kickoff=_time(packet["cutoff"]),_time(packet["kickoff"])
    if cutoff>=kickoff:
        raise ValueError("cutoff must precede kickoff")
    jc=packet["official_jc_signed_line"]
    if jc is not None and (type(jc) is not int or not -5<=jc<=5):
        raise ValueError("JC signed integer, NOT Asian quarter handicap")
    rows=packet["quotes"]
    if not isinstance(rows,list):
        raise ValueError("quotes list required")
    groups=defaultdict(list)
    seen=set()
    for raw in rows:
        q=_snapshot(raw,cutoff,kickoff)
        key=(q["bookmaker"],q["market"],q["at"])
        if key in seen:raise ValueError("duplicate bookmaker-market-time")
        seen.add(key)
        groups[(q["bookmaker"],q["market"])].append(q)
    for qs in groups.values():qs.sort(key=lambda r:r["at"])
    pair_by_market=defaultdict(dict)
    for (book,market), qs in groups.items():
        if len(qs)>=2 and (qs[-1]["at"]-qs[0]["at"]).total_seconds()>=600:
            pair_by_market[market][book]=(qs[0],qs[-1])
    # Snapshots within one source are never counted as distinct independent evidence.
    two_way=len(pair_by_market["1x2"])>=2
    latest_1x2=[v[-1] for v in pair_by_market["1x2"].values()]
    earliest_1x2=[v[0] for v in pair_by_market["1x2"].values()]
    flags=[]; details={}; favored=None
    if two_way:
        p_open=[_median_z(earliest_1x2,i) for i in range(3)]
        p_latest=[_median_z(latest_1x2,i) for i in range(3)]
        favored="home" if p_open[0]>=p_open[2] else "away"
        fi=0 if favored=="home" else 2
        underdog="away" if favored=="home" else "home"
        ui=2 if favored=="home" else 0
        dp_f=p_latest[fi]-p_open[fi]
        dp_u=p_latest[ui]-p_open[ui]
        details={"favorite":favored,"initial_book_median_probabilities":p_open,
                 "latest_book_median_probabilities":p_latest,
                 "favorite_delta_pp":round(dp_f*100,3),
                 "underdog_delta_pp":round(dp_u*100,3),
                 "books_compared":sorted(pair_by_market["1x2"])}
        # A single unusual book cannot trigger consensus evidence.
        books=pair_by_market["1x2"]
        drift_against=sum((last["probabilities"][fi]-first["probabilities"][fi])<=-.025 for first,last in books.values())
        cold_shortening=sum((last["probabilities"][ui]-first["probabilities"][ui])>=.025 for first,last in books.values())
        if dp_f<=-.03 and drift_against>=2:
            flags.append("FAVORITE_PROBABILITY_DRIFT_REVIEW_ONLY")
        if .10<=p_open[ui]<=.36 and dp_u>=.03 and cold_shortening>=2:
            flags.append("UNDERDOG_PRICE_SHORTENING_COLD_WATCH_ONLY")
        # Cross-market Asian quarter-line agreement: do not convert official JC integers.
        paired_books=set(books)&set(pair_by_market["asian"])
        adverse=[]; shallow=[]
        for book in paired_books:
            o,l=books[book]
            ao,al=pair_by_market["asian"][book]
            if abs((l["at"]-al["at"]).total_seconds())>3600:
                continue
            fdelta=l["probabilities"][fi]-o["probabilities"][fi]
            a0=(-ao["line_home"] if favored=="home" else ao["line_home"])
            a1=(-al["line_home"] if favored=="home" else al["line_home"])
            # favorite more likely in 1x2 but handicap burden eases >= quarter goal.
            if fdelta>=.025 and a1<=a0-.25:
                adverse.append(book)
            if p_latest[fi]>=.69 and a1<=.5:
                shallow.append(book)
        if len(adverse)>=2:
            flags.append("EURO_ASIAN_OPPOSITE_MOVES_REVIEW_ONLY")
        if len(shallow)>=2:
            flags.append("STRONG_FAVORITE_SHALLOW_ASIAN_LINE_REVIEW_ONLY")
        details["eurasian_usable_company_count"]=len(paired_books)
        details["eurasian_opposite_companies"]=sorted(adverse)
        details["low_odds_shallow_asian_companies"]=sorted(shallow)
    # Buy share is same correlated market family; need a genuinely earlier timestamp.
    crowd=packet["crowd"]
    if crowd is not None:
        if not isinstance(crowd,dict) or set(crowd)!={"observed_at","source_id","share_home","share_draw","share_away"}:
            raise ValueError("invalid crowd schema")
        ct=_time(crowd["observed_at"])
        if ct>cutoff or ct>=kickoff:
            raise ValueError("postcutoff crowd information prohibited")
        if not isinstance(crowd["source_id"],str) or not crowd["source_id"].strip():
            raise ValueError("crowd independent published source id required")
        ps=[_num(crowd[f"share_{s}"],0,1) for s in ("home","draw","away")]
        if abs(math.fsum(ps)-1)>1e-6:
            raise ValueError("crowd shares must sum to one")
        if two_way:
            chosen=ps[0 if favored=="home" else 2]
            if chosen>=.70 and details["favorite_delta_pp"]<=-3.0:
                flags.append("CROWD_HEAT_VS_MARKET_DRIFT_REVIEW_ONLY")
            details["favorite_buy_share"]=chosen
    ev=packet["independent_evidence"]
    if not isinstance(ev,list):raise ValueError("independent_evidence must be a list")
    validated=[]
    for z in ev:
        if not isinstance(z,dict) or set(z)!={"family","side","source_id","observed_at","impact"}:
            raise ValueError("invalid nonmarket fact")
        if z["family"] not in NONMARKET or z["side"] not in SIDES or z["impact"] not in ("favorable","adverse"):
            raise ValueError("nonmarket-only evidence families")
        if not isinstance(z["source_id"],str) or not z["source_id"].strip():
            raise ValueError("evidence source id missing")
        if _time(z["observed_at"])>cutoff:
            raise ValueError("postcutoff injury/tactics prohibited")
        validated.append(z)
    independent_support=False
    if two_way:
        other="away" if favored=="home" else "home"
        candidates={(z["family"],z["source_id"]) for z in validated
                    if (z["side"]==other and z["impact"]=="favorable") or
                       (z["side"]==favored and z["impact"]=="adverse")}
        independent_support=len({f for f,_ in candidates})>=2 and len({s for _,s in candidates})>=2
    if "UNDERDOG_PRICE_SHORTENING_COLD_WATCH_ONLY" in flags and independent_support:
        flags.append("COLD_SIDE_WITH_TWO_NONMARKET_FAMILIES_SECOND_REVIEW")
    h=sha256(json.dumps(packet,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if not two_way:
        status="INSUFFICIENT_BOOKMAKER_TIME_SERIES"
    elif flags:
        status="MARKET_DIVERGENCE_RESEARCH_REVIEW"
    else:
        status="NO_PRE_REGISTERED_MARKET_ALERT"
    return {"version":VERSION,"match_id":match_id,"status":status,
            "cutoff":packet["cutoff"],"official_jc_signed_line":jc,
            "european_1x2_two_or_more_paired_books":two_way,
            "asian_two_point_book_count":len(pair_by_market["asian"]),
            "odds_time_pair_count":{k:len(pair_by_market[k]) for k in sorted(MARKETS)},
            "features":details,"flags":flags,
            "nonmarket_independent_support":independent_support,
            "source_sha256":h,"intent_proven":False,"research_only":True,
            "auto_flip_wdl":False,"auto_change_q":False,"auto_core_grant":False,
            "production_mutated":False}


def no_historical_market_packet(match_id, cutoff, kickoff, official_jc_signed_line):
    return {"match_id":match_id,"cutoff":cutoff,"kickoff":kickoff,
            "official_jc_signed_line":official_jc_signed_line,
            "quotes":[],"crowd":None,"independent_evidence":[]}