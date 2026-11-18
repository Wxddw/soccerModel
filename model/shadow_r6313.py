"""R6.3.13 optional research channels layered over frozen R6.3.12.

No module writes Production parameters or uses match outcomes. Optional inputs:
research_candidate_model, research_htft, research_market_odds.
"""
from __future__ import annotations
import copy
import candidate_models_r6313 as models
import halftime_bridge_r6313 as halftime
import market_audit_r6313 as market
import shadow_r6312 as previous

VERSION='M79.3.6_SHADOW_R6.3.13_20261117'


def _prematch_spec(packet:dict,spec:dict,label:str)->None:
    if not isinstance(spec,dict):raise ValueError(label+' must be an object')
    if spec.get('kickoff')!=packet.get('kickoff'):
        raise ValueError(label+' kickoff must match packet kickoff')
    models.check_prematch_source(spec.get('source_id'),spec.get('observed_at'),spec.get('kickoff'))
    if models._asof(spec['observed_at'])>models._asof(packet['cutoff']):
        raise ValueError(label+' source is later than declared cutoff')


def inspect(packet:dict)->dict:
    if not isinstance(packet,dict):raise ValueError('prematch object required')
    original=copy.deepcopy(packet)
    parent=previous.inspect(packet)
    bridge=parent['S4_GS_RC_unified_probability_bridge_v312']
    flags=[]
    cand={'status':'NOT_REQUESTED','research_only':True}
    ht={'status':'BLOCK_NO_PREMATCH_FRACTION_OR_GRID','research_only':True}
    mk={'status':'NO_PREMATCH_MARKET_SNAPSHOT','research_only':True}
    if packet.get('research_candidate_model') is not None:
        _prematch_spec(packet,packet['research_candidate_model'],'candidate model')
        cand=models.generate_grid(packet['research_candidate_model'])
        if bridge.get('status')=='ONE_JOINT_GRID_VALIDATED':
            # Candidate must be separately evaluated: never adopt it as source Q.
            import joint_bridge_r6312 as joint
            c=joint.aggregate(cand['grid'],bridge.get('official_signed_jc_line'))
            cand={k:v for k,v in cand.items() if k!='grid'}
            cand['candidate_wdl']=c['wdl_probabilities']
            cand['candidate_goal_top3']=c['raw_goal_bucket_top3']
            cand['candidate_score_top3']=c['raw_score_top3']
            cand['wdl_delta_vs_frozen_grid']={k:c['wdl_probabilities'][k]-bridge['wdl_probabilities'][k] for k in joint.WDL}
        else:
            cand={k:v for k,v in cand.items() if k!='grid'}
            flags.append('CANDIDATE_CAN_NOT_REPLACE_MISSING_FROZEN_BASE_GRID')
    if packet.get('research_htft') is not None:
        spec=packet['research_htft']
        _prematch_spec(packet,spec,'halftime model')
        if set(spec)!={'fraction_home','fraction_away','source_id','observed_at','kickoff'}:
            raise ValueError('halftime model must specify calibrated fraction provenance')
        if bridge.get('status')=='ONE_JOINT_GRID_VALIDATED':
            ht=halftime.aggregate_htft(packet['score_matrix'],**spec)
        else:flags.append('HTFT_BLOCK_MISSING_FROZEN_JOINT_GRID')
    if packet.get('research_market_odds') is not None:
        spec=packet['research_market_odds']
        _prematch_spec(packet,spec,'market')
        wdl=bridge.get('wdl_probabilities') if bridge.get('status')=='ONE_JOINT_GRID_VALIDATED' else None
        mk=market.devig(spec,wdl)
    assert packet==original, 'prematch packet mutated'
    return {**parent,'version':VERSION,
        'research_candidate_grid_diagnostics_r6313':cand,
        'HTFT_conditional_transition_r6313':ht,
        'market_devig_r6313':mk,
        'research_flags_r6313':flags,
        'formal_single_grant':None,'formal_handicap_grant':None,
        'formal_core_grant':None,'formal_protection_grant':None,
        'production_changed':False,'probability_adjustment_applied':False,
        'no_automatic_candidate_adoption':True,
        'notes_r6313':['Candidate score models need independent prematch lambdas and samples.',
             'Halftime fractions require historical calibration and never update the full-time grid.',
             'Odds de-vig is a benchmark, not an override or calibrated truth.',
             'Production R6.3.12 and M79.3.6 weights untouched.']}
