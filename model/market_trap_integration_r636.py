"""Isolated SHADOW integration of Nov22 publication/exposure and Nov23 odds watch.

No Production M79.3.6 modules are imported or modified. The output retains
both audits separately: market odds cannot become an independent roster/tactics
family nor can market heat alone flip a frozen WDL pick.
"""
from __future__ import annotations
import copy
import hashlib
import json
from datetime import datetime
from market_trap_cold_watch_r636 import screen


def prematch_audit_with_market(existing_packet, market_packet, *, tail_evidence=None, aic_records=None):
    if not isinstance(existing_packet,dict) or not isinstance(market_packet,dict):
        raise ValueError('prematch packets required')
    # This bridge needs a pre-vetted full-Q publication record.  Do not replace
    # it with independent ad hoc market estimates or postmatch result records.
    if (existing_packet.get('match_id')!=market_packet.get('match_id') or
        existing_packet.get('cutoff')!=market_packet.get('cutoff') or
        existing_packet.get('kickoff')!=market_packet.get('kickoff') or
        existing_packet.get('official_jc_line')!=market_packet.get('official_jc_signed_line')):
        raise ValueError('time/match/official-line mismatch')
    from r636_exposure_guards_20261122 import prematch_exposure_review
    old=copy.deepcopy(existing_packet)
    market=copy.deepcopy(market_packet)
    a=prematch_exposure_review(existing_packet,tail_evidence=tail_evidence,aic_records=aic_records)
    b=screen(market_packet)
    if existing_packet!=old or market_packet!=market:
        raise AssertionError('pure prematch audit must not mutate inputs')
    return {'research_only':True,'formal_grant':None,
            'market':b,'existing_exposure':a,
            'independent_market_evidence_families':1,
            'market_can_authorize_auto_reversal':False,
            'production_mutated':False}