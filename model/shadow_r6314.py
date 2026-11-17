"""Read-only R6.3.14 research challenger using previously-fitted calibration only.

Current R6.3.13 and M79.3.6 outputs are never modified. Training labels and
actual results are prohibited in the prematch packet; candidate weights must be
fitted separately on completed, chronologically earlier fixtures.
"""
from __future__ import annotations
import copy
import calibration_r6314 as calibration
import shadow_r6313 as previous
import joint_bridge_r6312 as joint
from candidate_models_r6313 import _asof

VERSION='M79.3.6_SHADOW_R6.3.14_20261117'


def inspect(packet:dict)->dict:
    if not isinstance(packet,dict): raise ValueError('prematch packet required')
    if set(packet)&{'actual_score','result_score','final_score','half_time_score','postmatch','result','training_results'}:
        raise ValueError('postmatch labels prohibited inside prematch packet')
    p=copy.deepcopy(packet)
    # Crucially do not pass new optional calibration metadata to the original
    # Production/Shadow path: existing strict field checks may reject it.
    extension=p.pop('research_fitted_calibrations_r6314',None)
    parent=previous.inspect(p)
    base=parent['S4_GS_RC_unified_probability_bridge_v312']
    result={'status':'NO_TRAINED_CALIBRATION_ATTACHED','research_only':True}
    if extension is not None:
        if not isinstance(extension,dict) or not extension or set(extension)-{'margin','goal'}:
            raise ValueError('only goal/margin research calibration bundles accepted')
        if base['status']!='ONE_JOINT_GRID_VALIDATED':
            result={'status':'BLOCK_NO_FROZEN_JOINT_GRID','research_only':True}
        else:
            candidates={}
            for name,fit in extension.items():
                if not isinstance(fit,dict) or fit.get('axis')!=name or 'weights' not in fit:
                    raise ValueError('invalid fitted calibration')
                if not fit.get('research_only',False) or fit.get('formal_grant') is not None:
                    raise ValueError('formal model access forbidden')
                if _asof(fit['latest_training_kickoff'])>=_asof(p['cutoff']):
                    raise ValueError('training data cannot overlap prematch cutoff')
                q=calibration.apply(p['score_matrix'],fit)
                t=joint.aggregate(q,base['official_signed_jc_line'])
                candidates[name]={'candidate_wdl':t['wdl_probabilities'],
                                  'candidate_goals':t['goal_bucket_probabilities'],
                                  'candidate_score_top3':t['raw_score_top3'],
                                  'candidate_jc':t['jc_probabilities'],
                                  'change_from_frozen_wdl':{k:t['wdl_probabilities'][k]-base['wdl_probabilities'][k] for k in joint.WDL},
                                  'letdraw_warning':calibration.letdraw_warning(q,base['official_signed_jc_line'])
                                    if base['official_signed_jc_line'] is not None else None,
                                  'probability_conservation':t['joint_mass'],
                                  'train_count':fit.get('training_count'),
                                  'research_only':True,'automatic_adoption':False}
            result={'status':'RESEARCH_CALIBRATION_CHALLENGERS_ONLY','candidates':candidates,'research_only':True}
    if packet!=copy.deepcopy(packet): raise AssertionError('prematch mutation detected')
    return {**parent,'version':VERSION,'r6314_calibration_research':result,
            'production_changed':False,'formal_core_grant':None,
            'formal_handicap_grant':None,'formal_single_grant':None,
            'probability_adjustment_applied':False}
