"""Development-only ablation of local boundary localization, with duration LOMO."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation import possession_metrics as pm
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from scripts.evaluate_duration_model import uncensored_durations
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config,evaluate_reference
from src.p3_sequence_model import run


def play_sequence(labels, halves):
    codes=pm.label_codes(labels)
    halves=np.asarray(halves)
    edges=np.r_[0,np.flatnonzero(halves[1:]!=halves[:-1])+1,len(halves)]
    runs=[(int(a),int(b)) for a,b in zip(edges[:-1],edges[1:]) if halves[a]>0]
    filled=pm.fill_abstentions(codes,runs)
    return [k for _,_,k in pm.segments(filled,runs)]


def main():
    out=ROOT/'artifacts/boundary_refinement';out.mkdir(exist_ok=True)
    protocol=json.loads((ROOT/'configs/skillcorner_protocol.json').read_text())
    blobs=json.loads((ROOT/'configs/skillcorner_source_blobs.json').read_text())
    names=['src/boundary_refinement.py','src/p3_sequence_model.py','src/duration_model.py',
        'src/control_evidence.py','src/p2_deadball_detector.py','src/skillcorner_validation.py',
        'src/learned_control_cache.py','scripts/evaluate_duration_model.py',
        'scripts/evaluate_boundary_refinement.py','evaluation/possession_metrics.py',
        'configs/skillcorner_protocol.json']
    sources={n:digest(ROOT/n) for n in names}
    plan={'sources':sources,'localization':'fixed +/-1-second window, clean confirmed control order, midpoint of bracket',
        'duration_scale':'leave-one-development-match-out; final scale all development matches',
        'primary_comparison':'duration_refined versus duration',
        'standalone_ablation':'original_refined versus original; no alternative promotion selection',
        'gate':'primary mean spellF1 gain >=0.01, >=8 wins, paired 90% lower bound >0',
        'public_or_comparison_tuning':False}
    (out/'protocol.json').write_text(json.dumps(plan,indent=2))
    data,means={},{}
    for match in protocol['development_matches']:
        folder=ROOT/'artifacts/external/skillcorner'/match
        tracking=verify_source(folder,match,protocol,blobs)
        a,b,ref=load_cached(folder,protocol,ROOT/'artifacts/learned_control/feature_cache'/match,tracking)
        data[match]=a,b,ref
        means[match]=float(uncensored_durations(ref,a.half,protocol['source_fps']).mean())
    rows=[]
    for match,(a,b,ref) in data.items():
        scale=float(np.mean([value for other,value in means.items() if other!=match]))
        baselines={}
        for mode in ('original','original_refined','duration','duration_refined'):
            cfg=native_config(protocol,'sustained_control')
            if mode.startswith('duration'):
                cfg['hmm']['decoder']='duration'
                cfg['duration']={'scale_seconds':scale,'fps':protocol['source_fps']}
            if mode.endswith('_refined'):
                cfg['boundary_refinement']={'enabled':True,'fps':protocol['source_fps']}
            c=run(cfg,a,b)
            family=mode.removesuffix('_refined')
            if mode==family:
                baselines[family]=c.raw_label
                changed=0
            else:
                changed=int((c.raw_label!=baselines[family]).sum())
                if play_sequence(c.raw_label,a.half)!=play_sequence(baselines[family],a.half):
                    raise AssertionError('Refinement changed the full-play state sequence')
            m=evaluate_reference(ref,c.raw_label,a.half,protocol['source_fps'])
            rows.append({'match':match,'mode':mode,'spellF1':m['partial_reference_spellF1'],
                'macroF1_HA':m['macroF1_HA'],'precision_05':m['per_iou'][.5]['precision'],
                'recall_05':m['per_iou'][.5]['recall'],'changed_frames':changed,
                'transition_f1_1s':m['transitions']['1.0']['f1']})
        pd.DataFrame(rows).to_csv(out/'development.csv',index=False)
        print(match+': four-way ablation complete, full-play label sequences preserved',flush=True)
    frame=pd.DataFrame(rows);comparisons={}
    pivot=frame.pivot(index='match',columns='mode',values='spellF1')
    for family in ('original','duration'):
        delta=(pivot[family+'_refined']-pivot[family]).to_numpy()
        interval=np.quantile(np.random.default_rng(0).choice(delta,(10000,len(delta))).mean(axis=1),[.05,.95])
        comparisons[family]={'mean_gain':float(delta.mean()),'wins':int((delta>0).sum()),
            'paired_match_bootstrap_90pct':interval.tolist(),
            'gate_passed':bool(delta.mean()>=.01 and (delta>0).sum()>=8 and interval[0]>0)}
    cfg=yaml.safe_load((ROOT/'configs/control_candidate.yaml').read_text())
    cfg['hmm']['decoder']='duration'
    cfg['duration']={'scale_seconds':float(np.mean(list(means.values()))),'fps':25}
    cfg['boundary_refinement']={'enabled':True,'fps':25}
    for key in ('spatial','deadball','predictions','overrides','submission','evaluation_results','evaluation_reports'):
        cfg['paths'][key]='artifacts/boundary_refinement_candidate/'+Path(cfg['paths'][key]).name
    (ROOT/'configs/boundary_refinement_candidate.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
    if sources!={n:digest(ROOT/n) for n in names}:
        raise RuntimeError('Experiment source changed during evaluation')
    report={'sources':sources,'summary':frame.groupby('mode').mean(numeric_only=True).to_dict(),
        'comparisons':comparisons,'primary_development_gate_passed':comparisons['duration']['gate_passed'],
        'full_play_label_sequences_preserved':True,'public_or_eight_evaluated':False,'promoted':False}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__': main()
