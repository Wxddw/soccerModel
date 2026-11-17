"""Build a narrow transparent paired development replay from already archived user files.
Never use final-score strings to construct or modify pre-match probabilities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile
from selection_efficiency_r633 import paired_audit, recommend

DIR = Path(__file__).resolve().parent
SRC = DIR.parent
REPORT = SRC / 'football_replay_20261017_22_report.md'
MID = SRC / 'M79_20261017_统一晚场分析_1821.md'
ZIP = SRC / 'M79_RC23_FSR_GS_研究修订与配对验证_20261021.zip'


def source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract() -> tuple[list[dict],dict]:
    if not (REPORT.exists() and MID.exists() and ZIP.exists()):
        snapshot = DIR / 'paired_input_DEV_ONLY_41.json'
        if snapshot.exists():
            rows=json.loads(snapshot.read_text(encoding='utf-8'))
            assert len(rows)==41 and all(x.get('split')=='development' for x in rows)
            return rows, {'source_notes': ['Bundled archival development-only replay snapshot; external source files unavailable for independent byte-level recheck'],
                          'n': len(rows), 'sale_n': sum(x['prematch']['ordinary_sale'] for x in rows),
                          'formal_performance_eligible': False}
        raise FileNotFoundError('Need source archived files or bundled paired_input_DEV_ONLY_41.json')
    lines = REPORT.read_text(encoding='utf-8').splitlines()
    score = {}
    for line in lines:
        m = re.match(r'^\|\s*(10-\d\d-\d{3})\s*\|.*?\|\s*(\d+):(\d+)\s*\|', line)
        if m:
            score[m.group(1)] = [int(m.group(2)),int(m.group(3))]
    assert len(score) == 41, f'expected 41 score lines, got {len(score)}'
    # 17 Oct: only a rounded WDL total-table is available in this workspace.
    md = MID.read_text(encoding='utf-8').splitlines()
    prematches = []
    for line in md:
        cols = [x.strip() for x in line.split('|')[1:-1]]
        if len(cols) < 6 or not re.fullmatch(r'0\d\d', cols[0]): continue
        rid = cols[0]
        if not (7 <= int(rid) <= 30): continue
        if not re.fullmatch(r'\d+(\.\d+)?/\d+(\.\d+)?/\d+(\.\d+)?',cols[3]): continue
        p = [float(x)/100 for x in cols[3].split('/')]
        t = cols[1].split(' ')[0]  # 10-17 or 10-18
        hour = cols[1].split(' ')[1]
        kickoff = f'2026-{t}T{hour}:00+08:00'
        prematches.append({
            'id':rid,'date':'10-17','cutoff':'2026-10-17T18:21:48+08:00',
            'kickoff':kickoff,'probabilities':p,
            'ordinary_sale':'普通未售' not in cols[4],
            'evidence':[],
            'origin': 'OCT17_MARKDOWN_ROUNDED_WDL_NO_FULL_JOINT',
            'archived_observation_proxy': '观察' in cols[4] and '普通未售' not in cols[4],
            'name': cols[2]})
    assert len(prematches) == 24, f'expected 24 October 17 rows, got {len(prematches)}'
    with zipfile.ZipFile(ZIP) as z:
        for date in ('10-19','10-20'):
            path = f'analysis_tmp/upgrade_20261021/frozen_oct{date[-2:]}.json'
            archive = json.loads(z.read(path))
            cutoff = archive['cutoff']
            for item in archive['predictions']:
                prob = item['M79']['probabilities']
                assert item['M79']['raw_top1'] == ('3','1','0')[max(range(3),key=lambda i: prob[i])], item['id']
                prematches.append({
                    'id':item['id'],'date':date, 'cutoff':cutoff,
                    'kickoff':item['kickoff'], 'probabilities':prob,
                    'ordinary_sale':item['sale_status']=='OPEN_AT_CUTOFF',
                    'evidence':[], 'origin':'FROZEN_UNCALIBRATED_MARKET_IPF_WDL',
                    'name':item['home']+'—'+item['away'],
                    'archive_freeze_hash':archive['freeze_hash'],
                    'archived_observation_proxy':item['M79']['selection']=='OBSERVE' and item['sale_status']=='OPEN_AT_CUTOFF'})
    assert len(prematches) == 41
    for pre in prematches:
        check = recommend(pre)
        if check['reference_proxy_eligible'] != pre['archived_observation_proxy']:
            raise ValueError(f"Archived observation flag mismatch: {pre['date']}-{pre['id']}")
    keys = [x['date']+'-'+x['id'] for x in prematches]
    assert len(keys)==len(set(keys)) and set(keys)==set(score), 'Score/prediction population mismatch'
    data=[{'prematch':{k:v for k,v in x.items() if k not in ('origin','name','archive_freeze_hash')},
           'actual_score':score[x['date']+'-'+x['id']], 'split':'development'} for x in prematches]
    provenance = {
        'source_report_sha256':source_hash(REPORT),'source_md_oct17_sha256':source_hash(MID),
        'source_zip_10_19_20_sha256':source_hash(ZIP),
        'source_notes': ['10-17: 24 rounded probabilities in 18:21 frozen markdown; no verified Q supplied',
                         '10-19 and 10-20: 17 frozen market/IPF reference matrices (not full M79 model)',
                         'Scores joined from development replay report; this is NOT an independent holdout'],
        'n':len(data), 'sale_n':sum(x['prematch']['ordinary_sale'] for x in data),
        'dates':['2026-10-17','2026-10-19','2026-10-20'],
        'reference_observation_labels_matched': 41, 'formal_performance_eligible':False
    }
    return data,provenance


def main():
    rows, provenance = extract()
    result = paired_audit(rows)
    result['provenance'] = provenance
    (DIR/'paired_development_41.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (DIR/'paired_input_DEV_ONLY_41.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('matches',len(rows),'sales',provenance['sale_n'])
    for k in ('reference_observation_proxy','shadow_probability_only_potential','recovery_n','recovery_hits',
              'recovery_misses','recoveries','raw_top1_hits_sale','core_structural_opportunities','core_evidence_verified',
              'mean_brier_reference','mean_logloss_reference'):
        print(k,result[k])

if __name__=='__main__':main()
