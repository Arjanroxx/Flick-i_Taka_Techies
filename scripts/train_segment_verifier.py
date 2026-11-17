"""Train against counterfactual segment utility; all scored matches remain held out."""
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
from src.skillcorner_validation import native_config,evaluate_reference,labelled_runs
from src.p3_sequence_model import run
from src.segment_verifier import propose,apply_proposals,fit_model,predict,canonical_digest,FEATURES


def utility_targets(reference, labels, halves, proposals):
    """Exact global spellF1 delta via the only scored run affected by an insertion."""
    gt,raw=pm.label_codes(reference),pm.label_codes(labels)
    runs=labelled_runs(gt,np.asarray(halves))
    filled=pm.fill_abstentions(raw,runs)
    global_metrics=pm.spell_scores(gt,filled,runs)
    gt_count,pred_count=global_metrics['n_gt'],global_metrics['n_pred']
    local_cache={};rows=[]
    for index,p in enumerate(proposals):
        window=next(((a,b) for a,b in runs if a<p['start']<p['stop']<b),None)
        if window is None:
            continue
        a,b=window;local_runs=[(0,b-a)]
        if window not in local_cache:
            local_cache[window]=pm.spell_scores(gt[a:b],filled[a:b],local_runs)
        old=local_cache[window]
        changed=raw[a:b].copy()
        span=changed[p['start']-a:p['stop']-a]
        span[span==p['owner']]=p['opponent']
        changed=pm.fill_abstentions(changed,local_runs)
        new=pm.spell_scores(gt[a:b],changed,local_runs)
        denominator=gt_count+pred_count+new['n_pred']-old['n_pred']
        scores=[]
        for iou in pm.SPELL_IOUS:
            tp=global_metrics['per_iou'][iou]['n_matched']+new['per_iou'][iou]['n_matched']-old['per_iou'][iou]['n_matched']
            scores.append(2*tp/denominator if denominator else 0.)
        delta=float(np.mean(scores)-global_metrics['mean_f1'])
        rows.append({'proposal':index,'gain':delta,'positive':int(delta>1e-12)})
    return rows


def fold_splits(matches):
    if len(matches)!=12 or len(set(matches))!=12:
        raise ValueError('Expected twelve unique development matches')
    splits=[]
    for fold in range(3):
        validation=[m for i,m in enumerate(matches) if i%3==fold]
        rest=[m for m in matches if m not in validation]
        splits.append({'fold':fold,'fit':rest[:-2],'calibration':rest[-2:],'validation':validation})
    return splits


def main():
    out=ROOT/'artifacts/segment_verifier';out.mkdir(exist_ok=True)
    protocol=json.loads((ROOT/'configs/skillcorner_protocol.json').read_text())
    plan=json.loads((ROOT/'configs/segment_verifier_protocol.json').read_text())
    blobs=json.loads((ROOT/'configs/skillcorner_source_blobs.json').read_text())
    names=['src/segment_verifier.py','scripts/train_segment_verifier.py','src/p3_sequence_model.py',
        'src/duration_model.py','src/control_evidence.py','src/p2_deadball_detector.py',
        'src/skillcorner_validation.py','src/learned_control_cache.py','scripts/evaluate_duration_model.py',
        'evaluation/possession_metrics.py','configs/skillcorner_protocol.json','configs/segment_verifier_protocol.json']
    sources={name:digest(ROOT/name) for name in names}
    (out/'protocol_lock.json').write_text(json.dumps({'sources':sources,'plan':plan},indent=2))
    matches=protocol['development_matches']
    if set(matches)&set(protocol['test_matches']):
        raise ValueError('Development/comparison overlap')
    splits=fold_splits(matches)
    data,means,cache={},{},{}
    for match in matches:
        folder=ROOT/'artifacts/external/skillcorner'/match
        tracking=verify_source(folder,match,protocol,blobs)
        a,b,ref=load_cached(folder,protocol,ROOT/'artifacts/learned_control/feature_cache'/match,tracking)
        data[match]=a,b,ref
        means[match]=float(uncensored_durations(ref,a.half,protocol['source_fps']).mean())
    def prepare(match,scale):
        key=match,scale
        if key not in cache:
            a,b,ref=data[match]
            cfg=native_config(protocol,'sustained_control');cfg['hmm']['decoder']='duration'
            cfg['duration']={'scale_seconds':scale,'fps':protocol['source_fps']}
            c=run(cfg,a,b)
            settings={'fps':protocol['source_fps'],'long_spell_seconds':scale}
            proposals=propose(c,a,b,cfg['hmm']['emission_temperature'],cfg['control'],settings)
            metrics=evaluate_reference(ref,c.raw_label,a.half,protocol['source_fps'])
            cache[key]={'c':c,'proposals':proposals,'baseline':metrics}
            print(match+': label-free segment features prepared',flush=True)
        return cache[key]
    def fit(fit_matches,scale):
        xs,ys,weights,stats=[],[],[],[]
        for match in fit_matches:
            pack=prepare(match,scale);a,b,ref=data[match]
            targets=utility_targets(ref,pack['c'].raw_label,a.half,pack['proposals'])
            stats.append({'match':match,'proposals':len(pack['proposals']),'labelled':len(targets),
                'positive':sum(row['positive'] for row in targets)})
            if targets:
                xs.extend(pack['proposals'][row['proposal']]['features'] for row in targets)
                ys.extend(row['positive'] for row in targets)
                weights.extend([1/len(targets)]*len(targets))
        return fit_model(xs,ys,weights),stats
    def calibrate(model,calibration,scale):
        packs={m:prepare(m,scale) for m in calibration}
        scores={m:predict(model,p['proposals']) for m,p in packs.items()}
        all_scores=np.concatenate(list(scores.values()))
        thresholds=[plan['disabled_threshold']]
        if len(all_scores):
            thresholds+=np.quantile(all_scores,plan['threshold_quantiles']).tolist()
        rows=[]
        for threshold in sorted(set(thresholds)):
            metrics=[]
            for match,pack in packs.items():
                labels=apply_proposals(pack['c'].raw_label,pack['proposals'],scores[match],threshold)
                a,b,ref=data[match]
                metrics.append(evaluate_reference(ref,labels,a.half,protocol['source_fps']))
            rows.append({'threshold':float(threshold),
                'spellF1':float(np.mean([r['partial_reference_spellF1'] for r in metrics])),
                'macroF1_HA':float(np.mean([r['macroF1_HA'] for r in metrics]))})
        selected=max(rows,key=lambda row:(row['spellF1'],row['macroF1_HA'],row['threshold']))
        model=dict(model,threshold=selected['threshold'])
        return model,rows
    rows,fold_records=[],[]
    for split in splits:
        fit_matches,calibration,validation=(split[k] for k in ('fit','calibration','validation'))
        assert not (set(fit_matches)&set(calibration) or set(validation)&set(fit_matches+calibration))
        scale=float(np.mean([means[m] for m in fit_matches]))
        model,stats=fit(fit_matches,scale)
        model,calibration_scores=calibrate(model,calibration,scale)
        model.update(fit_matches=fit_matches,calibration_matches=calibration,excluded_validation_matches=validation)
        (out/('fold'+str(split['fold'])+'_model.json')).write_text(json.dumps(model,indent=2))
        fold_records.append({**split,'scale_seconds':scale,'training_stats':stats,'calibration_scores':calibration_scores,
            'selected_threshold':model['threshold'],'model_kind':model['kind']})
        for match in validation:
            pack=prepare(match,scale);a,b,ref=data[match]
            changed=apply_proposals(pack['c'].raw_label,pack['proposals'],predict(model,pack['proposals']),model['threshold'])
            before=pack['c'].raw_label.to_numpy()
            if not np.array_equal(before=='D',changed=='D') or not np.array_equal(before=='X',changed=='X'):
                raise AssertionError('Verifier changed D or X')
            metrics=evaluate_reference(ref,changed,a.half,protocol['source_fps'])
            for mode,m in (('duration',pack['baseline']),('segment_verifier',metrics)):
                rows.append({'match':match,'fold':split['fold'],'mode':mode,'spellF1':m['partial_reference_spellF1'],
                    'macroF1_HA':m['macroF1_HA'],'precision_05':m['per_iou'][.5]['precision'],
                    'recall_05':m['per_iou'][.5]['recall'],'proposals':len(pack['proposals']),
                    'changed_frames':int((before!=changed).sum()) if mode=='segment_verifier' else 0})
            pd.DataFrame(rows).to_csv(out/'development.csv',index=False)
        print('fold '+str(split['fold'])+': held-out segment evaluation complete',flush=True)
    frame=pd.DataFrame(rows);pivot=frame.pivot(index='match',columns='mode',values='spellF1')
    delta=(pivot.segment_verifier-pivot.duration).to_numpy()
    interval=np.quantile(np.random.default_rng(0).choice(delta,(10000,len(delta))).mean(axis=1),[.05,.95])
    gate=plan['development_gate']
    passes=bool(delta.mean()>=gate['mean_spell_gain'] and (delta>0).sum()>=gate['minimum_match_wins']
                and interval[0]>gate['paired_bootstrap_lower_bound'])
    fit_matches,calibration=matches[:-2],matches[-2:]
    final_scale=float(np.mean([means[m] for m in fit_matches]))
    model,stats=fit(fit_matches,final_scale)
    model,calibration_scores=calibrate(model,calibration,final_scale)
    model.update(fit_matches=fit_matches,calibration_matches=calibration,
        target='positive exact counterfactual partial-reference spellF1 gain; scores are not calibrated probabilities',
        source_revision=protocol['revision'],training_protocol_sha256=digest(ROOT/'configs/segment_verifier_protocol.json'))
    (ROOT/'models').mkdir(exist_ok=True)
    (ROOT/'models/segment_verifier.json').write_text(json.dumps(model,indent=2))
    cfg=yaml.safe_load((ROOT/'configs/control_candidate.yaml').read_text());cfg['hmm']['decoder']='duration'
    cfg['duration']={'scale_seconds':final_scale,'fps':25}
    cfg['segment_verifier']={'enabled':True,'fps':25,'long_spell_seconds':final_scale,
        'model_path':'models/segment_verifier.json','model_canonical_sha256':canonical_digest(model)}
    for key in ('spatial','deadball','predictions','overrides','submission','evaluation_results','evaluation_reports'):
        cfg['paths'][key]='artifacts/segment_verifier_candidate/'+Path(cfg['paths'][key]).name
    (ROOT/'configs/segment_verifier_candidate.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
    if sources!={name:digest(ROOT/name) for name in names}:
        raise RuntimeError('Sources changed during training/evaluation')
    report={'sources':sources,'folds':fold_records,'summary':frame.groupby('mode').mean(numeric_only=True).to_dict(),
        'mean_spell_gain':float(delta.mean()),'wins':int((delta>0).sum()),'paired_match_bootstrap_90pct':interval.tolist(),
        'development_gate_passed':passes,'final_fit_matches':fit_matches,'final_calibration_matches':calibration,
        'final_scale_seconds':final_scale,'final_training_stats':stats,'final_calibration_scores':calibration_scores,
        'final_threshold':model['threshold'],'final_model_canonical_sha256':canonical_digest(model),
        'public_or_eight_evaluated':False,'fresh_compatible_D_reference_available':False,'promoted':False}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__': main()
