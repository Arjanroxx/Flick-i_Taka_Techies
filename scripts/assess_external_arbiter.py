"""Run the P4 Nov 11 assessment on pinned public Metrica Sample Game 1 tracking."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlopen

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_local_arbiter import LOCAL_SETTINGS, MODEL, fingerprint, select_windows
from src import p3_sequence_model
from src.contracts import SCHEMAS
from src.p4_arbiter_and_eval import METRICA_SAMPLE_REVISION, apply_overrides, local_arbiter
from src.p4_external_sample import PITCH_M, SAMPLE_ROOT_URL, TRACKING_FILES, load_external_features


def download_sample(folder):
    folder.mkdir(parents=True, exist_ok=True)
    sources = {name: f"data/Sample_Game_1/{name}" for name in TRACKING_FILES.values()}
    sources["README.source.md"] = "README.md"
    for name, source in sources.items():
        target = folder / name
        if target.exists():
            continue
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                with urlopen(f"{SAMPLE_ROOT_URL}/{source}", timeout=60) as response:
                    shutil.copyfileobj(response, temporary)
            except BaseException:
                temporary.close()
                temporary_path.unlink(missing_ok=True)
                raise
        temporary_path.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "artifacts/external/metrica")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/p4/nov11/external_run")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--max-window-frames", type=int, default=125)
    args = parser.parse_args()
    if args.limit <= 0 or args.max_window_frames <= 0:
        parser.error("Window limits must be positive")
    if args.download:
        download_sample(args.data_dir)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))
    threshold = config["thresholds"]["entropy"]
    confidence = config["thresholds"]["override_confidence"]
    if (not np.isfinite(threshold) or not 0 <= threshold <= np.log(3)
            or not np.isfinite(confidence) or not 0 <= confidence <= 1):
        parser.error("Invalid entropy or confidence threshold")
    sources = {team: {"file": name, "sha256": fingerprint(args.data_dir / name),
                       "url": f"{SAMPLE_ROOT_URL}/data/Sample_Game_1/{name}"}
               for team, name in TRACKING_FILES.items()}
    spatial, deadball = load_external_features(args.data_dir)
    if any(fingerprint(args.data_dir / value["file"]) != value["sha256"]
           for value in sources.values()):
        raise RuntimeError("External inputs changed during loading")
    predictions = p3_sequence_model.run(config, spatial, deadball)
    halves = spatial.half
    windows = select_windows(predictions, threshold, args.limit, args.max_window_frames,
                             halves=halves)
    responses, requests = [], []
    for window in windows:
        proposals = local_arbiter(spatial, deadball, predictions, window,
                                  halves=halves, **LOCAL_SETTINGS)
        accepted = proposals.loc[proposals.confidence >= confidence]
        responses.append(accepted)
        requests.append({
            "window": list(window),
            "inputs": {kind: json.loads(table.loc[window[0]:window[1]].to_json(
                orient="split", double_precision=15)) for kind, table in (
                    ("spatial", spatial), ("deadball", deadball), ("predictions", predictions))},
            "proposals": json.loads(proposals.to_json(orient="records")),
            "accepted": json.loads(accepted.to_json(orient="records")),
            "decision": "override" if len(accepted) else "retain_base",
        })
    overrides = (pd.concat(responses, ignore_index=True) if responses else pd.DataFrame({
        name: pd.Series(dtype=dtype) for name, dtype in SCHEMAS["overrides"].items()
    }))
    labels = apply_overrides(predictions, overrides, confidence)
    if not labels.index.equals(spatial.index) or not labels.isin(list("HADX")).all():
        raise ValueError("External labels do not match the sample timeline")
    cache = {
        "model": MODEL, "settings": LOCAL_SETTINGS, "entropy_threshold": threshold,
        "minimum_confidence": confidence, "window_limit": args.limit,
        "max_window_frames": args.max_window_frames, "sequence_settings": config["hmm"],
        "sequence_thresholds": config["thresholds"], "source_revision": METRICA_SAMPLE_REVISION,
        "sources": sources, "pitch_m": PITCH_M.tolist(), "requests": requests,
        "source_sha256": {name: fingerprint(ROOT / name) for name in (
            "src/p4_external_sample.py", "src/p4_arbiter_and_eval.py", "src/p3_sequence_model.py",
            "scripts/run_local_arbiter.py", "scripts/assess_external_arbiter.py")},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as temporary:
        stage = Path(temporary)
        spatial.to_parquet(stage / "external_spatial.parquet")
        deadball.to_parquet(stage / "external_deadball.parquet")
        predictions.to_parquet(stage / "external_predictions.parquet")
        overrides.to_parquet(stage / "external_overrides.parquet", index=False)
        predictions.raw_label.rename("label").to_csv(stage / "baseline.csv")
        labels.to_csv(stage / "with_overrides.csv")
        (stage / "response_cache.json").write_text(
            json.dumps(cache, indent=2, allow_nan=False), encoding="utf-8")
        summary = {
            "source": "Metrica Sports Sample Game 1", "frames": len(spatial),
            "periods": sorted(int(value) for value in halves.unique()),
            "windows_reviewed": len(windows), "proposals": sum(len(r["proposals"]) for r in requests),
            "overrides_accepted": len(overrides), "changed_frames": int((labels != predictions.raw_label).sum()),
            "confidence_threshold": confidence, "possession_accuracy_measured": False,
            "outputs": {path.name: fingerprint(path) for path in sorted(stage.iterdir())},
        }
        (stage / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        args.out.mkdir(parents=True, exist_ok=True)
        for path in stage.iterdir():
            if path.name != "summary.json":
                path.replace(args.out / path.name)
        (stage / "summary.json").replace(args.out / "summary.json")
    print(json.dumps({key: value for key, value in summary.items() if key != "outputs"}, indent=2))


if __name__ == "__main__":
    main()
