"""Learned segment-utility verifier. Inference never receives reference labels."""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from evaluation import possession_metrics as pm
from .control_evidence import sustained_control_evidence

FEATURES = ['duration_s','parent_duration_s','duration_ratio','opponent_distance_m',
    'opponent_advantage_m','opponent_preference_fraction','opponent_confirmed_fraction',
    'moving_fraction','stationary_fraction','mean_ball_speed','std_ball_speed',
    'median_opponent_distance_rate','base_opponent_probability','base_owner_probability',
    'base_entropy','abstention_fraction','missing_fraction','return_delay_s',
    'previous_owner_delay_s','proposed_contact_s']


def canonical_digest(model):
    return hashlib.sha256(json.dumps(model,sort_keys=True,separators=(',',':'),
        allow_nan=False).encode()).hexdigest()


def propose(predictions, spatial, deadball, temperature, control, settings):
    fps, long_seconds = settings['fps'], settings['long_spell_seconds']
    if (not np.isfinite([fps,long_seconds]).all() or fps<=0 or long_seconds<=0
            or not predictions.index.equals(spatial.index)):
        raise ValueError('Invalid segment-proposal settings or alignment')
    n=len(spatial)
    raw=pm.label_codes(predictions.raw_label)
    halves,frames=spatial.half.to_numpy(),spatial.index.to_numpy()
    edges=np.r_[0,np.flatnonzero((halves[1:]!=halves[:-1])|(np.diff(frames)!=1))+1,n]
    runs=[(int(a),int(b)) for a,b in zip(edges[:-1],edges[1:]) if a<b and halves[a]>0]
    filled=pm.fill_abstentions(raw,runs)
    teams,known=sustained_control_evidence(spatial,deadball,temperature,control)
    strong=np.where(known,teams.argmax(axis=1),-1)
    d=spatial[['dist_nearest_H','dist_nearest_A']].to_numpy(dtype=float)
    observed=(np.isfinite(d).all(axis=1)
        & np.isfinite(spatial[['ball_x','ball_y']]).all(axis=1).to_numpy()
        & ~spatial.ball_is_imputed.to_numpy() & (spatial.gap_length_frames.to_numpy()==0))
    live=(deadball.is_dead_ball_prob.to_numpy()<=1/3+1e-7)&~deadball.is_out_of_bounds.to_numpy()
    contact=(observed & live & (d.min(axis=1)<=3.) & (np.abs(d[:,0]-d[:,1])>=.5))
    preference=d.argmin(axis=1)
    speed=spatial.ball_speed.to_numpy(dtype=float)
    probabilities=predictions[['prob_H','prob_A']].to_numpy(dtype=float)
    entropy=predictions.state_entropy.to_numpy(dtype=float)
    bracket=max(1,round(3*fps))
    minimum=control.get('confirmation_frames',3)
    proposals=[]
    for left,right,owner in pm.segments(filled,runs):
        if owner not in (pm.H,pm.A) or (right-left)/fps<long_seconds:
            continue
        opponent=1-owner
        flags=contact[left:right]&(preference[left:right]==opponent)
        breaks=np.flatnonzero(np.diff(np.r_[False,flags,False]))
        for start,end in zip(breaks[::2]+left,breaks[1::2]+left):
            if end-start<minimum:
                continue
            previous=np.flatnonzero(strong[max(left,start-bracket):start]==owner)
            following=np.flatnonzero(strong[end:min(right,end+bracket+1)]==owner)
            if not previous.size or not following.size:
                continue
            old=max(left,start-bracket)+previous[-1]
            stop=end+following[0]
            if start<=left or stop>=right or not live[old:stop+1].all():
                continue
            if not (raw[start:stop]==owner).any():
                continue
            valid=observed[start:stop]
            ds=d[start:stop]
            finite_speed=np.isfinite(speed[start:stop])&valid
            velocities=np.clip(speed[start:stop][finite_speed],0,40)
            rate=np.abs(np.diff(ds[:,opponent]))*fps
            pair=valid[1:]&valid[:-1]&np.isfinite(rate)
            count=stop-start
            mean=lambda values:float(np.mean(values)) if len(values) else 0.
            vector=[count/fps,min((right-left)/fps,120.),count/(right-left),
                mean(np.clip(ds[valid,opponent],0,30)),
                mean(np.clip(ds[valid,owner]-ds[valid,opponent],-12,12)),
                float((valid&(preference[start:stop]==opponent)).mean()),
                float((strong[start:stop]==opponent).mean()),
                float((finite_speed&(speed[start:stop]>=1)&(speed[start:stop]<=12)).mean()),
                float((finite_speed&(speed[start:stop]<.3)).mean()),mean(velocities),
                float(np.std(velocities)) if len(velocities) else 0.,
                float(np.median(np.clip(rate[pair],0,40))) if pair.any() else 0.,
                mean(probabilities[start:stop,opponent]),mean(probabilities[start:stop,owner]),
                mean(entropy[start:stop]),float((raw[start:stop]==pm.X).mean()),
                float((~valid).mean()),(stop-end)/fps,(start-old)/fps,(end-start)/fps]
            if not np.isfinite(vector).all():
                raise ValueError('Nonfinite segment features')
            proposals.append({'start':int(start),'stop':int(stop),'owner':int(owner),
                'opponent':int(opponent),'features':vector})
    return proposals


def apply_proposals(labels, proposals, scores, threshold):
    output=np.asarray(labels,dtype='<U1').copy()
    if len(proposals)!=len(scores) or not np.isfinite(scores).all() or not np.isfinite(threshold):
        raise ValueError('Invalid segment decision scores')
    accepted=[]
    for i in sorted(range(len(proposals)),key=lambda i:(-scores[i],proposals[i]['start'],i)):
        if scores[i]<threshold:
            continue
        candidate=proposals[i];start,stop=candidate['start'],candidate['stop']
        if (not 0<=start<stop<=len(output) or candidate['owner'] not in (pm.H,pm.A)
                or candidate['opponent']!=1-candidate['owner']):
            raise ValueError('Invalid possession-split interval or teams')
        if any(start<b and a<stop for a,b in accepted):
            continue
        owner=pm.LABELS[candidate['owner']]
        window=output[start:stop]
        window[window==owner]=pm.LABELS[candidate['opponent']]
        accepted.append((start,stop))
    return output


def fit_model(x,y,weights):
    x=np.asarray(x,dtype=float).reshape((-1,len(FEATURES)))
    y,weights=np.asarray(y,dtype=float),np.asarray(weights,dtype=float)
    if (len(x)!=len(y) or len(y)!=len(weights) or not np.isfinite(x).all()
            or not np.isin(y,[0,1]).all() or not np.isfinite(weights).all() or (weights<=0).any()):
        raise ValueError('Invalid segment-utility training examples')
    if not len(y) or len(np.unique(y))<2:
        return {'version':1,'features':FEATURES,'kind':'constant','score':float(y[0]) if len(y) else 0.}
    weights=weights/weights.sum()
    center=(x*weights[:,None]).sum(axis=0)
    scale=np.maximum(np.sqrt(((x-center)**2*weights[:,None]).sum(axis=0)),1e-3)
    z=np.column_stack([(x-center)/scale,np.ones(len(x))])
    def objective(coef):
        logits=z@coef
        loss=np.sum(weights*(np.logaddexp(0,logits)-y*logits))+.1*np.dot(coef[:-1],coef[:-1])/2
        grad=z.T@(weights*(expit(logits)-y));grad[:-1]+=.1*coef[:-1]
        return float(loss),grad
    result=minimize(objective,np.zeros(z.shape[1]),jac=True,method='L-BFGS-B',
                    options={'maxiter':300,'ftol':1e-10})
    if not result.success:
        raise ValueError('Segment-utility fitting failed: '+str(result.message))
    return {'version':1,'features':FEATURES,'kind':'logistic','center':center.tolist(),
        'scale':scale.tolist(),'coef':result.x[:-1].tolist(),'intercept':float(result.x[-1]),'ridge':.1}


def predict(model, proposals):
    if model.get('version')!=1 or model.get('features')!=FEATURES:
        raise ValueError('Incompatible segment model')
    if model.get('kind')=='constant':
        score=model['score']
        if not np.isfinite(score) or not 0<=score<=1:
            raise ValueError('Invalid constant segment score')
        return np.full(len(proposals),score)
    if model.get('kind')!='logistic':
        raise ValueError('Unknown segment model kind')
    center,scale,coef=(np.asarray(model[name],dtype=float) for name in ('center','scale','coef'))
    if (any(a.shape!=(len(FEATURES),) for a in (center,scale,coef))
            or not np.isfinite([center,scale,coef]).all() or (scale<=0).any()
            or not np.isfinite(model['intercept'])):
        raise ValueError('Invalid segment-model coefficients')
    x=np.asarray([p['features'] for p in proposals],dtype=float).reshape((-1,len(FEATURES)))
    return expit(((x-center)/scale)@coef+model['intercept'])


def refine_predictions(predictions, spatial, deadball, config):
    settings=config['segment_verifier']
    model=settings.get('model')
    if model is None:
        path=Path(settings['model_path'])
        if not path.is_absolute():
            path=Path(__file__).resolve().parents[1]/path
        model=json.loads(path.read_text(encoding='utf-8'))
        if canonical_digest(model)!=settings['model_canonical_sha256']:
            raise ValueError('Segment model checksum mismatch')
    proposals=propose(predictions,spatial,deadball,
        config['hmm'].get('emission_temperature',1.),config.get('control',{}),settings)
    scores=predict(model,proposals)
    return apply_proposals(predictions.raw_label,proposals,scores,model['threshold'])
