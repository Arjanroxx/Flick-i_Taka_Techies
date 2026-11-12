import json
import numpy as np
import pandas as pd
from pathlib import Path

from .contracts import BOUNDS, FRAME_COUNT, SCHEMAS, frame_halves, read, validate

METRICA_SAMPLE_REVISION = "e706dd506b360d69d9d123d5b8026e7294b13996"
METRICA_SAMPLE_URL = (
    "https://raw.githubusercontent.com/metrica-sports/sample-data/"
    + METRICA_SAMPLE_REVISION
    + "/data/Sample_Game_1/Sample_Game_1_RawEventsData.csv"
)


def load_metrica_events(path):
    """Load other-match event observations without inventing frame possession labels."""
    events = pd.read_csv(path, encoding="utf-8-sig")
    required = ["Team", "Type", "Period", "Start Frame", "End Frame",
                "Start Time [s]", "End Time [s]"]
    if not set(required).issubset(events.columns) or events.empty:
        raise ValueError("Expected a non-empty Metrica sample events CSV")
    for name in required[2:]:
        events[name] = pd.to_numeric(events[name], errors="raise")
        if not np.isfinite(events[name]).all():
            raise ValueError(f"Missing or non-finite Metrica event values in {name}")
    if not events.Team.isin(["Home", "Away"]).all() or events.Type.isna().any():
        raise ValueError("Unknown team or missing event type")
    frames = events[["Period", "Start Frame", "End Frame"]].to_numpy()
    if ((frames[:, 0] < 1).any() or (frames[:, 1:] < 0).any()
            or (frames != np.floor(frames)).any()):
        raise ValueError("Metrica periods must be positive and frames nonnegative integers")
    # Preserve source anomalies for assessment instead of silently repairing event labels.
    events.attrs["reversed_intervals"] = int((
        (events["End Frame"] < events["Start Frame"])
        | (events["End Time [s]"] < events["Start Time [s]"])
    ).sum())
    return events

def _unique_json_fields(pairs):
    record = dict(pairs)
    if len(record) != len(pairs):
        raise ValueError("Duplicate fields in arbiter response")
    return record


def parse_arbiter_response(response, window, *, halves=None):
    """Validate one local JSON response and return a Contract D row."""
    record = json.loads(response, object_pairs_hook=_unique_json_fields)
    schema = SCHEMAS["overrides"]
    if not isinstance(record, dict) or record.keys() != schema.keys():
        raise ValueError("Expected exactly start_frame, end_frame, override_label and confidence")
    start, end = record["start_frame"], record["end_frame"]
    if any(type(frame) is not int or frame < 0 for frame in (start, end)):
        raise ValueError("Frame bounds must be valid integer frame numbers")
    if halves is None and (start >= FRAME_COUNT or end >= FRAME_COUNT):
        raise ValueError("Frame bounds exceed the competition timeline")
    if not isinstance(record["override_label"], str):
        raise ValueError("Override label must be a string")
    confidence = record["confidence"]
    low, high = BOUNDS["confidence"]
    if type(confidence) not in (int, float) or not low <= confidence <= high:
        raise ValueError("Confidence must be a finite number from 0 to 1")
    if start < window[0] or end > window[1]:
        raise ValueError("Override must stay inside the requested window")
    table = pd.DataFrame([record]).astype(schema)
    if halves is None:
        return validate("overrides", table)
    if (not halves.index.is_unique or not halves.index.is_monotonic_increasing
            or start not in halves.index or end not in halves.index or start > end):
        raise ValueError("Override bounds must belong to the external timeline")
    segment = halves.loc[start:end]
    if (len(segment) != end - start + 1 or segment.iloc[0] <= 0
            or not segment.eq(segment.iloc[0]).all()):
        raise ValueError("Override must stay inside one external period")
    # External rows use D's field types with their own frame domain.
    if not table.override_label.isin(("H", "A", "D", "X")).all():
        raise ValueError("Unknown override label")
    return table


def find_windows(predictions, threshold, *, halves=None):
    windows = []
    frames = predictions.index.to_numpy()
    if halves is not None and not halves.index.equals(predictions.index):
        raise ValueError("External periods must align exactly with prediction frames")
    periods = frame_halves() if halves is None else halves.to_numpy()
    if (len(frames) != len(periods) or len(frames) == 0
            or not np.array_equal(frames, np.arange(frames[0], frames[0] + len(frames)))):
        raise ValueError("Window selection requires a complete contiguous frame index")
    for half in np.unique(periods[periods > 0]):
        selected = ((predictions.state_entropy.to_numpy() >= threshold)
                    & (periods == half))
        flagged = np.r_[False, selected, False]
        starts = np.flatnonzero(~flagged[:-1] & flagged[1:])
        ends = np.flatnonzero(flagged[:-1] & ~flagged[1:]) - 1
        windows.extend((int(frames[start]), int(frames[end])) for start, end in zip(starts, ends))
    return windows

def local_arbiter(spatial, deadball, predictions, window, *, min_observed_frames=3,
                  max_distance_m=2.0, min_margin_m=2.0, max_dead_probability=0.2, halves=None):
    """Propose team overrides from sustained observed proximity inside one request."""
    start, end = window
    evidence = spatial.loc[start:end]
    stops = deadball.loc[start:end]
    home = evidence.dist_nearest_H.to_numpy()
    away = evidence.dist_nearest_A.to_numpy()
    near = np.minimum(home, away)
    far = np.maximum(home, away)
    observed = (
        np.isfinite(evidence[["ball_x", "ball_y"]]).all(axis=1).to_numpy()
        & ~evidence.ball_is_imputed.to_numpy()
        & (evidence.gap_length_frames.to_numpy() == 0)
        & (evidence.half.to_numpy() != 0)
        & ~stops.is_out_of_bounds.to_numpy()
        & (stops.is_dead_ball_prob.to_numpy() <= max_dead_probability)
        & np.isfinite(home) & np.isfinite(away)
        & (near <= max_distance_m) & (far - near >= min_margin_m)
    )
    records = []
    for label, nearer in (("H", home < away), ("A", away < home)):
        flags = np.r_[False, observed & nearer, False]
        starts = np.flatnonzero(~flags[:-1] & flags[1:])
        ends = np.flatnonzero(flags[:-1] & ~flags[1:])
        for left, right in zip(starts, ends):
            first, last = int(start + left), int(start + right - 1)
            if (right - left < min_observed_frames
                    or predictions.raw_label.loc[first:last].eq(label).all()):
                continue
            # A proximity score with no probability calibration.
            score = float(np.min(far[left:right] / (near[left:right] + far[left:right])))
            response = json.dumps({"start_frame": first, "end_frame": last,
                                   "override_label": label, "confidence": score})
            records.append(parse_arbiter_response(response, window, halves=halves))
    if records:
        result = pd.concat(records, ignore_index=True).sort_values(
            ["start_frame", "end_frame"], ignore_index=True
        )
        return validate("overrides", result) if halves is None else result
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in SCHEMAS["overrides"].items()})


def extract_frame(video_path, frame):
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
        ok, image = capture.read()
        if not ok:
            raise ValueError(f"Cannot read video frame {frame}")
        return image
    finally:
        capture.release()

def run(config, predictions):
    # Reuse algorithm-generated overrides. Local arbitration remains P4 work; competition extracts cannot go to hosted LLMs.
    path = Path(config["paths"]["overrides"])
    if path.exists():
        return read("overrides", path)
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in SCHEMAS["overrides"].items()})

def apply_overrides(predictions, overrides, minimum_confidence):
    """Apply inclusive windows, with higher confidence winning overlaps."""
    labels = predictions.raw_label.copy()
    eligible = overrides[overrides.confidence >= minimum_confidence]
    for row in eligible.sort_values("confidence", kind="stable").itertuples(index=False):
        labels.loc[row.start_frame:row.end_frame] = row.override_label
    return labels.rename("label")
