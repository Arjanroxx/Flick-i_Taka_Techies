"""Post-fit ablation: no retraining, threshold selection or public scoring."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config,evaluate_reference
from src.p3_sequence_model import run
from src.segment_verifier import propose,apply_proposals,predict


def main():
    out=ROOT/'artifacts/segment_verifier'
    report=json.loads((out/'report.json').read_text())
    if report['sources']!={name:digest(ROOT/name) for name in report['sources']}:
        raise ValueError('Training sources changed')
    protocol=json.loads((ROOT/'configs/skillcorner_protocol.json').read_text())
    blobs=json.loads((ROOT/'configs/skillcorner_source_blobs.json').read_text())
    expected=pd.read_csv(out/'development.csv').set_index(['match','mode'])
    fingerprints={'scripts/assess_segment_proposals.py':digest(ROOT/'scripts/assess_segment_proposals.py')}
    rows=[]
    for fold in report['folds']:
        path=out/('fold'+str(fold['fold'])+'_model.json')
        fingerprints[str(path.relative_to(ROOT))]=digest(path)
        model=json.loads(path.read_text())
        if model['fit_matches']!=fold['fit'] or model['calibration_matches']!=fold['calibration']:
            raise ValueError('Fold model provenance differs')
        scale=fold['scale_seconds']
        for match in fold['validation']:
            if match in model['fit_matches']+model['calibration_matches']:
                raise ValueError('Validation match leakage')
            folder=ROOT/'artifacts/external/skillcorner'/match
            tracking=verify_source(folder,match,protocol,blobs)
            a,b,ref=load_cached(folder,protocol,ROOT/'artifacts/learned_control/feature_cache'/match,tracking)
            cfg=native_config(protocol,'sustained_control');cfg['hmm']['decoder']='duration'
            cfg['duration']={'scale_seconds':scale,'fps':protocol['source_fps']}
            c=run(cfg,a,b)
            settings={'fps':protocol['source_fps'],'long_spell_seconds':scale}
            proposals=propose(c,a,b,cfg['hmm']['emission_temperature'],cfg['control'],settings)
            variants={'duration':c.raw_label,
                'proposal_only':apply_proposals(c.raw_label,proposals,np.ones(len(proposals)),0.),
                'segment_verifier':apply_proposals(c.raw_label,proposals,predict(model,proposals),model['threshold'])}
            for mode,labels in variants.items():
                m=evaluate_reference(ref,labels,a.half,protocol['source_fps'])
                if mode!='proposal_only' and not np.isclose(m['partial_reference_spellF1'],
                        expected.loc[(int(match),mode),'spellF1'],atol=1e-12,rtol=0):
                    raise AssertionError('Frozen held-out scores failed to reproduce')
                rows.append({'match':match,'mode':mode,'spellF1':m['partial_reference_spellF1'],
                    'macroF1_HA':m['macroF1_HA'],'precision_05':m['per_iou'][.5]['precision'],
                    'recall_05':m['per_iou'][.5]['recall']})
            print(match+': frozen proposal-only ablation completed',flush=True)
    if fingerprints!={name:digest(ROOT/name) for name in fingerprints}:
        raise RuntimeError('Ablation source/model changed')
    frame=pd.DataFrame(rows);frame.to_csv(out/'proposal_ablation.csv',index=False)
    result={'no_retraining_or_selection':True,'training_sources':report['sources'],
        'ablation_fingerprints':fingerprints,'frozen_held_out_scores_reproduced':True,
        'summary':frame.groupby('mode')[['spellF1','macroF1_HA','precision_05','recall_05']].mean().to_dict(),
        'public_or_eight_evaluated':False}
    (out/'proposal_ablation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
