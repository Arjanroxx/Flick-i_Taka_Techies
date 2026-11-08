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

def parse_arbiter_response(response, window):
    """Validate one local JSON response and return a Contract D row."""
    record = json.loads(response)
    schema = SCHEMAS["overrides"]
    if not isinstance(record, dict) or record.keys() != schema.keys():
        raise ValueError("Expected exactly start_frame, end_frame, override_label and confidence")
    start, end = record["start_frame"], record["end_frame"]
    if any(type(frame) is not int or not 0 <= frame < FRAME_COUNT for frame in (start, end)):
        raise ValueError("Frame bounds must be valid integer frame numbers")
    if not isinstance(record["override_label"], str):
        raise ValueError("Override label must be a string")
    confidence = record["confidence"]
    low, high = BOUNDS["confidence"]
    if type(confidence) not in (int, float) or not low <= confidence <= high:
        raise ValueError("Confidence must be a finite number from 0 to 1")
    if start < window[0] or end > window[1]:
        raise ValueError("Override must stay inside the requested window")
    return validate("overrides", pd.DataFrame([record]).astype(schema))


def find_windows(predictions, threshold):
    windows = []
    for half in (1, 2):
        selected = ((predictions.state_entropy.to_numpy() >= threshold)
                    & (frame_halves() == half))
        flagged = np.r_[False, selected, False]
        starts = np.flatnonzero(~flagged[:-1] & flagged[1:])
        ends = np.flatnonzero(flagged[:-1] & ~flagged[1:]) - 1
        windows.extend(zip(starts, ends))
    return windows

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
        labels.iloc[row.start_frame:row.end_frame + 1] = row.override_label
    return labels.rename("label")
