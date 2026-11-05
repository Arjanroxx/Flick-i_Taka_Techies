import numpy as np
import pandas as pd
from pathlib import Path

from .contracts import SCHEMAS, frame_halves, read

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
