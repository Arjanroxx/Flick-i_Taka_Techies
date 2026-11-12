"""Adapt public Metrica CSV tracking to P3/P4 using the sample's own timeline."""
import csv
from pathlib import Path

import numpy as np
import pandas as pd

from .p4_arbiter_and_eval import METRICA_SAMPLE_REVISION

SAMPLE_ROOT_URL = (
    "https://raw.githubusercontent.com/metrica-sports/sample-data/" + METRICA_SAMPLE_REVISION
)
TRACKING_FILES = {team: f"Sample_Game_1_RawTrackingData_{team}_Team.csv"
                  for team in ("Home", "Away")}
PITCH_M = np.array([105.0, 68.0])


def load_side(path, team):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        teams = next(reader)
        next(reader)  # Shirt identifiers are metadata, not an extra observation row.
        header = next(reader)
    if (header[:3] != ["Period", "Frame", "Time [s]"] or len(header) < 7
            or (len(header) - 3) % 2 or header[-2:] != ["Ball", ""]
            or any(teams[i] != team or not header[i].startswith("Player")
                   for i in range(3, len(header) - 2, 2))):
        raise ValueError(f"Unexpected {team} tracking header")
    table = pd.read_csv(path, skiprows=2)
    values = table.apply(pd.to_numeric, errors="raise").to_numpy(dtype="float64")
    if not len(values) or np.isinf(values).any() or not np.isfinite(values[:, :3]).all():
        raise ValueError("Tracking needs finite frame/time metadata and finite-or-missing coordinates")
    periods, frames = values[:, 0], values[:, 1]
    if ((periods < 1).any() or (periods != np.floor(periods)).any()
            or not np.array_equal(frames, np.arange(frames[0], frames[0] + len(frames)))
            or frames[0] < 0):
        raise ValueError("Expected positive integer periods and ordered contiguous frame identifiers")
    if (np.diff(periods) < 0).any():
        raise ValueError("Tracking periods must remain in play order")
    steps = np.diff(values[:, 2])[np.diff(periods) == 0]
    if len(steps) and not np.allclose(steps, 1 / 25, atol=1e-5):
        raise ValueError("Sample time steps disagree with 25 fps")
    return values


def load_external_features(folder):
    home = load_side(Path(folder) / TRACKING_FILES["Home"], "Home")
    away = load_side(Path(folder) / TRACKING_FILES["Away"], "Away")
    if (len(home) != len(away) or not np.array_equal(home[:, :3], away[:, :3])
            or not np.allclose(home[:, -2:], away[:, -2:], equal_nan=True)):
        raise ValueError("Home and Away tracking timelines or ball observations disagree")
    index = pd.Index(home[:, 1].astype("int64"), name="frame")
    ball = home[:, -2:] * PITCH_M
    observed = np.isfinite(ball).all(axis=1)
    ball[~observed] = np.nan
    spatial = pd.DataFrame({"half": home[:, 0].astype("int8"),
                            "ball_x": ball[:, 0], "ball_y": ball[:, 1],
                            "ball_is_imputed": False}, index=index)
    missing = pd.Series(~observed, index=index)
    groups = (missing.ne(missing.shift()) | spatial.half.ne(spatial.half.shift())).cumsum()
    spatial["gap_length_frames"] = missing.groupby(groups).transform("size").where(missing, 0).astype("int32")
    for label, values in (("H", home), ("A", away)):
        players = values[:, 3:-2].reshape(len(values), -1, 2) * PITCH_M
        distances = np.linalg.norm(players - ball[:, None, :], axis=2)
        nearest = np.where(np.isfinite(distances), distances, np.inf).min(axis=1)
        spatial[f"dist_nearest_{label}"] = np.where(np.isfinite(nearest), nearest, np.nan)
    for column in ("ball_x", "ball_y", "dist_nearest_H", "dist_nearest_A"):
        spatial[column] = spatial[column].astype("float32")
    outside = observed & ((ball < 0) | (ball > PITCH_M)).any(axis=1)
    # Weak boundary evidence only. In-bounds stoppages remain a documented limitation.
    probability = np.where(outside, 0.98, np.where(observed, 0.05, 0.5)).astype("float32")
    deadball = pd.DataFrame({"is_dead_ball_prob": probability,
                            "is_out_of_bounds": outside}, index=index)
    return spatial, deadball
