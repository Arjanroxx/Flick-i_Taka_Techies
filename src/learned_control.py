"""Small symmetric control classifier using geometry only, trained on other games."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.special import expit

from .control_evidence import sustained_control_evidence

FEATURE_NAMES = ['margin', 'log_distance_ratio', 'relative_margin', 'contact_difference',
                 'advantage_velocity', 'distance_stability', 'contact_moving', 'contact_decelerating',
                 *[f'{kind}_history_{seconds}' for seconds in (.2, .6, 1.5)
                   for kind in ('margin', 'contact', 'stable_contact')]]


def control_features(spatial, deadball, fps):
    """Causal, team-antisymmetric features. Never accepts possession labels.

    Distance stability while the ball moves is a co-motion proxy, not a reliable
    player-velocity measurement. Histories reset at periods and frame gaps.
    """
    if fps <= 0 or not np.isfinite(fps) or not spatial.index.equals(deadball.index):
        raise ValueError('Invalid native frame rate or feature alignment')
    d = spatial[['dist_nearest_H', 'dist_nearest_A']].to_numpy(dtype=float)
    valid = (np.isfinite(d).all(axis=1)
             & np.isfinite(spatial[['ball_x', 'ball_y']]).all(axis=1).to_numpy()
             & ~spatial.ball_is_imputed.to_numpy() & (spatial.gap_length_frames.to_numpy() == 0)
             & (spatial.half.to_numpy() > 0))
    margin = np.where(valid, np.clip(d[:, 1] - d[:, 0], -12, 12), 0.)
    ratio = np.where(valid, np.clip(np.log((d[:, 1] + .25) / (d[:, 0] + .25)), -4, 4), 0.)
    relative = np.where(valid, (d[:, 1] - d[:, 0]) / (d.sum(axis=1) + .5), 0.)
    contact = np.where(valid, np.exp(-(d[:, 0] / 2)**2) - np.exp(-(d[:, 1] / 2)**2), 0.)
    periods, frames = spatial.half.to_numpy(), spatial.index.to_numpy()
    edges = np.r_[0, np.flatnonzero((periods[1:] != periods[:-1]) | (np.diff(frames) != 1)) + 1, len(spatial)]
    speed = spatial.ball_speed.to_numpy(dtype=float)
    moving = np.nan_to_num(np.clip(speed / 15, 0, 1), nan=0.)
    trend = np.zeros(len(spatial)); stability = np.zeros(len(spatial)); slowing = np.zeros(len(spatial))
    history = np.zeros((len(spatial), 9))
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop - start > 1:
            pair = valid[start + 1:stop] & valid[start:stop - 1]
            derivative = np.diff(d[start:stop], axis=0) * fps
            trend[start + 1:stop] = np.where(pair, np.clip(derivative[:, 1] - derivative[:, 0], -20, 20), 0.)
            stability[start + 1:stop] = np.where(pair, np.clip(np.abs(derivative[:, 1]) - np.abs(derivative[:, 0]), -20, 20), 0.)
            slowing[start + 1:stop] = np.nan_to_num(np.clip((speed[start:stop - 1] - speed[start + 1:stop]) * fps / 40, -1, 1), nan=0.)
        values = np.column_stack([margin[start:stop], contact[start:stop],
                                  contact[start:stop] * (1 - moving[start:stop])])
        values[~valid[start:stop]] = np.nan
        for index, seconds in enumerate((.2, .6, 1.5)):
            window = max(1, round(seconds * fps))
            history[start:stop, index * 3:index * 3 + 3] = pd.DataFrame(values).rolling(
                window, min_periods=1).mean().fillna(0).to_numpy()
    features = np.column_stack([margin, ratio, relative, contact, trend, stability,
                                 contact * moving, contact * slowing, history])
    if not np.isfinite(features).all():
        raise ValueError('Nonfinite classifier features')
    eligible = (valid & (d.min(axis=1) <= 2) & ~deadball.is_out_of_bounds.to_numpy()
                & (deadball.is_dead_ball_prob.to_numpy() <= .2))
    return features, eligible


def fit_model(x, labels, weights, ridge):
    """Weighted logistic regression; no intercept enforces team-swap symmetry."""
    x, labels, weights = np.asarray(x), np.asarray(labels), np.asarray(weights)
    if (x.ndim != 2 or x.shape[1] != len(FEATURE_NAMES) or len(labels) != len(x)
            or not len(x) or not np.isfinite(x).all() or not np.isin(labels, [-1, 1]).all()
            or len(weights) != len(x) or (weights <= 0).any() or not np.isfinite(weights).all()
            or not np.isfinite(ridge) or ridge <= 0):
        raise ValueError('Invalid classifier training data')
    weights = weights / weights.sum()
    scale = np.sqrt(np.sum(x*x * weights[:, None], axis=0))
    scale = np.maximum(scale, 1e-3)
    standardized = x / scale
    def objective(coef):
        signed = labels * (standardized @ coef)
        loss = float(np.sum(weights * np.logaddexp(0, -signed)) + ridge * np.dot(coef, coef) / 2)
        gradient = standardized.T @ (-weights * labels * expit(-signed)) + ridge * coef
        return loss, gradient
    result = minimize(objective, np.zeros(x.shape[1]), jac=True, method='L-BFGS-B',
                      options={'maxiter': 150, 'ftol': 1e-10})
    if not result.success:
        raise ValueError('Classifier fit failed: ' + str(result.message))
    return {'version': 1, 'features': FEATURE_NAMES, 'scale': scale.tolist(),
            'coef': result.x.tolist(), 'temperature': 1., 'ridge': ridge}


def logits(model, x):
    if model.get('version') != 1 or model.get('features') != FEATURE_NAMES:
        raise ValueError('Incompatible learned-control model')
    scale, coef = np.asarray(model['scale']), np.asarray(model['coef'])
    if (scale.shape != (len(FEATURE_NAMES),) or coef.shape != scale.shape
            or not np.isfinite([scale, coef]).all() or (scale <= 0).any()
            or not np.isfinite(model['temperature']) or model['temperature'] <= 0):
        raise ValueError('Invalid classifier coefficients or calibration')
    return np.asarray(x) / scale @ coef


def calibrate_model(model, x, labels, weights):
    z = logits(model, x)
    weights = np.asarray(weights) / np.sum(weights)
    labels = np.asarray(labels)
    result = minimize_scalar(lambda log_t: float(np.sum(
        weights * np.logaddexp(0, -labels * z / np.exp(log_t)))),
        bounds=(np.log(.25), np.log(4)), method='bounded')
    if not result.success:
        raise ValueError('Probability calibration failed')
    return {**model, 'temperature': float(np.exp(result.x))}


def predict_model(model, x):
    return expit(logits(model, x) / model['temperature'])


def learned_control_evidence(spatial, deadball, temperature, control, settings):
    teams, known = sustained_control_evidence(spatial, deadball, temperature, control)
    model = settings.get('model')
    if model is None:
        path = Path(settings['model_path'])
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != settings['model_sha256']:
            raise ValueError('Learned model checksum mismatch')
        model = json.loads(content)
    threshold = settings.get('confidence', .85)
    fps = settings.get('fps', 25.)
    if not .5 < threshold < 1:
        raise ValueError('Invalid learned control confidence threshold')
    x, eligible = control_features(spatial, deadball, fps)
    probability = np.clip(predict_model(model, x), .05, .95)
    extra = eligible & ~known & (np.maximum(probability, 1 - probability) >= threshold)
    preference = np.where(extra, (probability < .5).astype(int), -1)
    halves, frames = spatial.half.to_numpy(), spatial.index.to_numpy()
    boundaries = np.r_[0, np.flatnonzero((preference[1:] != preference[:-1])
                         | (halves[1:] != halves[:-1]) | (np.diff(frames) != 1)) + 1, len(spatial)]
    for start, stop in zip(boundaries[:-1], boundaries[1:]):
        if stop > start and preference[start] >= 0 and stop - start >= control.get('confirmation_frames', 3):
            teams[start:stop, 0] = probability[start:stop]
            teams[start:stop, 1] = 1 - probability[start:stop]
            known[start:stop] = True
    return teams, known
