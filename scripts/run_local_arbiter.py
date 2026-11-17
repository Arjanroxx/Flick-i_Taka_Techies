"""Dry-run deterministic local arbitration on a bounded sample of P3's disputed windows."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.contracts import SCHEMAS, read, validate, write
from src.p4_arbiter_and_eval import apply_overrides, find_windows, local_arbiter

MODEL = "observed_proximity_v1"
LOCAL_SETTINGS = {"min_observed_frames": 3, "max_distance_m": 2.0,
                  "min_margin_m": 2.0, "max_dead_probability": 0.2}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_windows(predictions, threshold, limit, max_frames, *, halves=None):
    windows = find_windows(predictions, threshold, halves=halves)
    ranked = sorted(windows, key=lambda pair: (
        -float(predictions.state_entropy.loc[pair[0]:pair[1]].max()), pair[0]
    ))
    selected = []
    for start, end in ranked[:limit]:
        # Centre a bounded request on the peak entropy of each disjoint source interval.
        peak = int(predictions.state_entropy.loc[start:end].idxmax())
        left = max(start, min(peak - max_frames // 2, end - max_frames + 1))
        selected.append((int(left), int(min(end, left + max_frames - 1))))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/p4/nov10/dry_run")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-window-frames", type=int, default=125)
    args = parser.parse_args()
    if args.limit <= 0 or args.max_window_frames <= 0:
        parser.error("Window limits must be positive")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))
    paths = {name: (ROOT / config["paths"][name]).resolve()
             for name in ("spatial", "deadball", "predictions")}
    input_hashes = {kind: fingerprint(path) for kind, path in paths.items()}
    tables = {kind: read(kind, path) for kind, path in paths.items()}
    if any(fingerprint(path) != input_hashes[kind] for kind, path in paths.items()):
        raise RuntimeError("A handoff changed while being read. Retry with stable input files.")
    threshold = config["thresholds"]["entropy"]
    confidence = config["thresholds"]["override_confidence"]
    if not np.isfinite(threshold) or not 0 <= threshold <= np.log(3):
        parser.error("Entropy threshold must be finite and between 0 and log(3)")
    if not np.isfinite(confidence) or not 0 <= confidence <= 1:
        parser.error("Override confidence must be finite and between 0 and 1")
    spatial = tables["spatial"]
    deadball = tables["deadball"]
    predictions = tables["predictions"]
    settings = LOCAL_SETTINGS.copy()
    windows = select_windows(predictions, threshold, args.limit, args.max_window_frames)
    responses, requests = [], []
    for window in windows:
        proposals = local_arbiter(spatial, deadball, predictions, window, **settings)
        accepted = proposals.loc[proposals.confidence >= confidence]
        responses.append(accepted)
        requests.append({
            "window": list(window),
            "inputs": {kind: json.loads(table.loc[window[0]:window[1]].to_json(
                orient="split", double_precision=15))
                       for kind, table in tables.items()},
            "proposals": json.loads(proposals.to_json(orient="records")),
            "accepted": json.loads(accepted.to_json(orient="records")),
            "decision": "override" if len(accepted) else "retain_base",
            "reason": ("supported_observed_proximity" if len(accepted) else
                       "no_supported_change" if proposals.empty else "score_below_threshold"),
        })
    overrides = (pd.concat(responses, ignore_index=True) if responses else pd.DataFrame({
        name: pd.Series(dtype=dtype) for name, dtype in SCHEMAS["overrides"].items()
    }))
    validate("overrides", overrides)
    labels = apply_overrides(predictions, overrides, confidence)
    cache = {
        "model": MODEL, "settings": settings, "entropy_threshold": threshold,
        "minimum_confidence": confidence, "limit": args.limit,
        "max_window_frames": args.max_window_frames,
        "inputs": {kind: {"path": str(path), "sha256": input_hashes[kind]}
                   for kind, path in paths.items()},
        "source_sha256": {name: fingerprint(ROOT / name) for name in (
            "src/p4_arbiter_and_eval.py", "scripts/run_local_arbiter.py")},
        "requests": requests,
    }
    # Stage and validate the complete dry run before publishing its output files.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as temporary:
        stage = Path(temporary)
        write("overrides", overrides, stage / "llm_overrides.parquet")
        (stage / "response_cache.json").write_text(
            json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8"
        )
        predictions.raw_label.rename("label").to_csv(stage / "baseline.csv")
        labels.to_csv(stage / "with_overrides.csv")
        validator = ROOT / config["paths"]["validator"]
        for name in ("baseline.csv", "with_overrides.csv"):
            subprocess.run([sys.executable, str(validator), str(stage / name)],
                           cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        summary = {
            "model": MODEL, "windows_reviewed": len(windows),
            "overrides_accepted": len(overrides),
            "changed_frames": int((labels != predictions.raw_label).sum()),
            "csv_validation": "passed",
            "outputs": {path.name: fingerprint(path) for path in sorted(stage.iterdir())},
        }
        (stage / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        args.out.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            if path.name != "summary.json":
                path.replace(args.out / path.name)
        (stage / "summary.json").replace(args.out / "summary.json")
    print("Local arbitration dry run and both CSV validations passed. Evidence saved locally.")


if __name__ == "__main__":
    main()
