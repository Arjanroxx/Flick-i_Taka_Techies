"""Reproducible P3 fixture experiments, real-data diagnostics and handoff export.

Synthetic spells are generated with fixed seeds and carry their own state labels.
The public five-minute ground truth is not read here: it is reserved for the final
pipeline sanity check. External Metrica tracking has no frame-level possession
labels, so it supports descriptive runs only, never spellF1/macroF1 claims.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evaluation.possession_metrics as pm
from src import p3_sequence_model as p3
from src.contracts import frame_halves, read
from src.p3_synthetic import generate

METRIC_KEYS = (
    "macro_f1", "spell_f1_mean", "accuracy", "n_gt_spells", "n_pred_spells",
    "mean_spell_duration_s", "gt_mean_spell_duration_s", "fragmentation",
)
TRANSITION_RATIO = np.array([[0, 2, 3], [2, 0, 3], [5, 5, 0]], dtype=float)
TRANSITION_RATIO /= TRANSITION_RATIO.sum(axis=1, keepdims=True)


def transition(persistence):
    return np.where(np.eye(3, dtype=bool), persistence,
                    (1 - persistence) * TRANSITION_RATIO).tolist()


def variant(base, *, temperature=None, persistence=None, decoder=None):
    config = copy.deepcopy(base)
    if temperature is not None:
        config["hmm"]["emission_temperature"] = temperature
    if persistence is not None:
        config["hmm"]["transition"] = transition(persistence)
    if decoder is not None:
        config["hmm"]["decoder"] = decoder
    return config


def score(truth, labels):
    result = pm.evaluate(pm.label_codes(truth), pm.label_codes(labels))
    return {key: float(result[key]) for key in METRIC_KEYS}


def segments(labels):
    values = np.asarray(labels)
    return int((values[1:] != values[:-1]).sum() + 1)


def aggregate(rows):
    frame = pd.DataFrame(rows)
    summary = frame[list(METRIC_KEYS)].agg(["mean", "std"]).T
    return {
        name: {"mean": float(summary.loc[name, "mean"]),
               "std": float(summary.loc[name, "std"])}
        for name in METRIC_KEYS
    }


def synthetic_suite(base, seeds):
    datasets = {seed: generate(seed) for seed in seeds}
    baseline = {}
    for seed, (spatial, deadball, truth) in datasets.items():
        prediction = p3.run(base, spatial, deadball)
        baseline[seed] = score(truth, prediction.raw_label)

    def sweep(name, variants):
        rows = {variant_name: {} for variant_name in variants}
        for seed, (spatial, deadball, truth) in datasets.items():
            for variant_name, config in variants.items():
                prediction = p3.run(config, spatial, deadball)
                rows[variant_name][seed] = score(truth, prediction.raw_label)
        return {
            variant_name: {
                "per_seed": {str(seed): value for seed, value in per_seed.items()},
                "aggregate": aggregate(list(per_seed.values())),
            }
            for variant_name, per_seed in rows.items()
        }

    temperatures = sweep("temperature", {
        f"temperature_{value}": variant(base, temperature=value)
        for value in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0)
    })
    transitions = sweep("transition", {
        f"persistence_{value}": variant(base, persistence=value)
        for value in (0.990, 0.995, 0.997, 0.998, 0.999)
    })
    decoders = sweep("decoder", {
        "posterior": variant(base, decoder="posterior"),
        "viterbi": variant(base, decoder="viterbi"),
    })
    candidates = {
        "previous_baseline": variant(base, temperature=1.0, persistence=0.995,
                                     decoder="posterior"),
        "final_settings": base,
        "temp3_p999_posterior": variant(base, temperature=3.0, persistence=0.999,
                                        decoder="posterior"),
        "temp6_p999_viterbi": variant(base, temperature=6.0, persistence=0.999,
                                      decoder="viterbi"),
        "temp3_p995_viterbi": variant(base, temperature=3.0, persistence=0.995,
                                      decoder="viterbi"),
    }
    combined = sweep("combined", candidates)
    return {
        "seeds": list(seeds),
        "baseline": {
            "per_seed": {str(seed): value for seed, value in baseline.items()},
            "aggregate": aggregate(list(baseline.values())),
        },
        "temperature": temperatures,
        "transition": transitions,
        "decoder": decoders,
        "combined": combined,
    }


def imputation_checks(spatial, config):
    short_gap = config["thresholds"]["short_gap"]
    halves = frame_halves()
    imputed = spatial.ball_is_imputed.to_numpy()
    missing = ~np.isfinite(spatial[["ball_x", "ball_y"]].to_numpy()).all(axis=1)
    gap = spatial.gap_length_frames.to_numpy()
    edges = np.r_[0, np.flatnonzero(imputed[1:] != imputed[:-1]) + 1, len(imputed)]
    runs = [(int(start), int(stop)) for start, stop in zip(edges[:-1], edges[1:])
            if imputed[start]]
    checks = {
        "imputed_frames": int(imputed.sum()),
        "imputed_runs": len(runs),
        "max_imputed_run": max((stop - start for start, stop in runs), default=0),
        "longest_allowed": int(short_gap),
        "all_runs_within_short_gap": all(stop - start <= short_gap for start, stop in runs),
        "all_runs_inside_one_half": all(
            halves[start] != 0 and halves[start] == halves[stop - 1]
            for start, stop in runs
        ),
        "imputed_without_coordinates": int((imputed & missing).sum()),
        "imputed_gap_length_mismatch": int(
            sum((gap[start:stop] != stop - start).sum() for start, stop in runs)
        ),
        "imputed_with_finite_speed": int(
            (imputed & np.isfinite(spatial.ball_speed.to_numpy())).sum()
        ),
        "missing_unimputed_frames": int((~imputed & missing).sum()),
        "cross_half_gap_claims": int(
            sum((halves[start] != halves[stop - 1]) for start, stop in runs)
        ),
    }
    teams, known = p3.team_evidence(spatial)
    checks["imputed_team_evidence_is_neutral"] = bool(
        np.allclose(teams[imputed], 0.5) and not known[imputed].any()
    )
    checks["short_gap_shield_can_apply"] = bool(
        spatial.gap_length_frames.between(1, short_gap).to_numpy()[imputed].all()
    )
    return checks


def real_diagnostics(base, previous, paths, out):
    spatial = read("spatial", paths["spatial"])
    deadball = read("deadball", paths["deadball"])
    results, predictions = {}, {}
    for name, config in (("candidate", base), ("previous", previous)):
        prediction = p3.run(config, spatial, deadball)
        predictions[name] = prediction
        labels = prediction.raw_label.to_numpy()
        results[name] = {
            "label_counts": {label: int((labels == label).sum()) for label in "HADX"},
            "segments": segments(labels),
            "live_segments": segments(labels[labels != "X"]),
            "entropy_mean": float(prediction.state_entropy.mean()),
            "entropy_p95": float(prediction.state_entropy.quantile(0.95)),
            "entropy_max": float(prediction.state_entropy.max()),
        }
    results["changed_frames"] = int(
        (predictions["previous"].raw_label != predictions["candidate"].raw_label).sum()
    )
    results["disagreement_share"] = float(
        (predictions["previous"].raw_label != predictions["candidate"].raw_label).mean()
    )
    # Disputed-window queues at the configured threshold and at diagnostic thresholds.
    from src.p4_arbiter_and_eval import find_windows

    queues = {}
    exported = None
    for threshold in (0.9, 0.7, 0.5):
        windows = find_windows(predictions["candidate"], threshold)
        queues[str(threshold)] = {
            "windows": len(windows),
            "frames": int(sum(stop - start + 1 for start, stop in windows)),
        }
        if threshold == 0.5:
            exported = windows
    results["disputed_windows"] = queues
    if exported is not None:
        pd.DataFrame(exported, columns=["start_frame", "end_frame"]).to_csv(
            out / "disputed_windows.csv", index=False
        )
    return results


def external_baseline(base, folder):
    if not folder.is_dir():
        return {"status": "blocked", "reason": "external tracking folder not downloaded"}
    from src.p4_external_sample import load_external_features

    spatial, deadball = load_external_features(folder)
    prediction = p3.run(base, spatial, deadball)
    labels = prediction.raw_label.to_numpy()
    return {
        "status": "descriptive run only",
        "reason": "Metrica Sample Game 1 has no frame-level possession ground truth",
        "frames": int(len(spatial)),
        "label_counts": {label: int((labels == label).sum()) for label in "HADX"},
        "segments": segments(labels),
        "files": sorted(path.name for path in folder.iterdir()),
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/p3/experiments")
    parser.add_argument("--extern", type=Path, default=ROOT / "artifacts/p3/external/metrica")
    parser.add_argument("--skip-synthetic", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))

    result = {"config": config, "config_sha256": digest(args.config)}
    if not args.skip_synthetic:
        result["synthetic"] = synthetic_suite(config, args.seeds)
        summaries = []
        for experiment in ("temperature", "transition", "decoder", "combined"):
            for name, value in result["synthetic"][experiment].items():
                row = {"experiment": experiment, "variant": name}
                row.update({key: value["aggregate"][key]["mean"] for key in METRIC_KEYS})
                summaries.append(row)
        pd.DataFrame(summaries).to_csv(args.out / "synthetic_summary.csv", index=False)

    paths = {name: (ROOT / value).resolve() for name, value in config["paths"].items()}
    result["imputation"] = imputation_checks(read("spatial", paths["spatial"]), config)
    previous = variant(config, temperature=1.0, persistence=0.995, decoder="posterior")
    result["real"] = real_diagnostics(config, previous, paths, args.out)
    result["external"] = external_baseline(config, args.extern)

    (args.out / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps({
        "synthetic_baseline": result.get("synthetic", {}).get("baseline", {}).get(
            "aggregate", {}),
        "imputation": result["imputation"],
        "real": result["real"],
        "external": result["external"],
    }, indent=2))


if __name__ == "__main__":
    main()
