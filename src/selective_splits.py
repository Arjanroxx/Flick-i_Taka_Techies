"""Propose local opponent contacts, verify movement, then split only long H/A runs.

All evidence comes from tracking: the checks are complementary, not independent
sensors or calibrated probabilities of controlled possession.
"""
import numpy as np
from .control_evidence import sustained_control_evidence


def split_verified_possessions(labels, spatial, deadball, temperature, control, settings):
    fps = settings['fps']
    long_seconds = settings['long_spell_seconds']
    if not np.isfinite([fps, long_seconds]).all() or fps <= 0 or long_seconds <= 0:
        raise ValueError('Selective splitting requires positive FPS and long-spell scale')
    labels = np.asarray(labels)
    if len(labels) != len(spatial):
        raise ValueError('Split labels and tracking must align')
    result = labels.copy()
    teams, known = sustained_control_evidence(spatial, deadball, temperature, control)
    strong = np.where(known, teams.argmax(axis=1), -1)
    d = spatial[['dist_nearest_H','dist_nearest_A']].to_numpy(dtype=float)
    preference = d.argmin(axis=1)
    frames, halves = spatial.index.to_numpy(), spatial.half.to_numpy()
    observed = (np.isfinite(d).all(axis=1)
        & np.isfinite(spatial[['ball_x','ball_y']]).all(axis=1).to_numpy()
        & ~spatial.ball_is_imputed.to_numpy() & (spatial.gap_length_frames.to_numpy()==0)
        & (halves>0) & ~deadball.is_out_of_bounds.to_numpy()
        & (deadball.is_dead_ball_prob.to_numpy()<=.2))
    # Proposal is deliberately broader than original confirmed control. A
    # proposal alone never causes a label change.
    contact = observed & (d.min(axis=1)<=2.) & (np.abs(d[:,0]-d[:,1])>=.5)
    speed = spatial.ball_speed.to_numpy()
    moving = np.isfinite(speed) & (speed>=1.) & (speed<=12.)
    confirmation = max(2, int(np.ceil(.4*fps)))
    bracket = max(1, int(round(fps)))
    edges = np.r_[0,np.flatnonzero((labels[1:]!=labels[:-1])
        | (halves[1:]!=halves[:-1]) | (np.diff(frames)!=1))+1,len(labels)]
    for left,right in zip(edges[:-1],edges[1:]):
        if left==right or labels[left] not in ('H','A') or (right-left)/fps<long_seconds:
            continue
        owner = int(labels[left]=='A')
        candidate = contact[left:right] & (preference[left:right]!=owner)
        changes = np.flatnonzero(np.diff(np.r_[False,candidate,False]))
        accepted_stop = left
        for a,b in zip(changes[::2]+left,changes[1::2]+left):
            if b-a<confirmation or a<accepted_stop:
                continue
            opponent = 1-owner
            stable = moving[a:b].copy()
            stable[1:] &= np.abs(np.diff(d[a:b,opponent]))*fps<=2.
            stable_edges = np.flatnonzero(np.diff(np.r_[False,stable,False]))
            verified = [(a+x,a+y) for x,y in zip(stable_edges[::2],stable_edges[1::2])
                        if y-x>=confirmation]
            if not verified:
                continue
            start = verified[0][0]
            before = np.flatnonzero(strong[max(left,start-bracket):start]==owner)
            after = np.flatnonzero(strong[b:min(right,b+bracket+1)]==owner)
            if not before.size or not after.size:
                continue
            previous = max(left,start-bracket)+before[-1]
            stop = b+after[0]
            # The owner must bracket a fully observed, live interval. Never
            # manufacture a split from imputation, a missing gap or a stoppage.
            if (start<=left or stop>=right or not observed[previous:stop+1].all()
                    or not (halves[previous:stop+1]==halves[start]).all()
                    or not (np.diff(frames[previous:stop+1])==1).all()):
                continue
            result[start:stop] = 'A' if opponent else 'H'
            accepted_stop = stop
    return result
