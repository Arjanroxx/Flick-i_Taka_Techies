import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
import yaml

from scripts.run_local_arbiter import select_windows
from src.p4_arbiter_and_eval import apply_overrides, find_windows, local_arbiter, parse_arbiter_response
from src.p4_external_sample import TRACKING_FILES, load_external_features

ROOT = Path(__file__).resolve().parents[1]


def tracking_fixture(folder, *, missing_frames=(), away_offset=0):
    """One player per side and a shared ball on an intentionally different frame domain."""
    for team, player_x in (("Home", 0.49), ("Away", 0.9)):
        with (folder / TRACKING_FILES[team]).open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["", "", "", team, "", "", ""])
            writer.writerow(["", "", "", "1", "", "", ""])
            writer.writerow(["Period", "Frame", "Time [s]", "Player1", "", "Ball", ""])
            for offset in range(12):
                frame = 200000 + offset
                coordinates = (float("nan"), float("nan")) if frame in missing_frames else (0.5, 0.5)
                writer.writerow([1 if offset < 6 else 2,
                                 frame + (away_offset if team == "Away" else 0),
                                 round((offset + 1) / 25, 2), player_x, 0.5, *coordinates])


class ExternalArbiterTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "artifacts").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        tracking_fixture(self.folder)
        self.spatial, self.deadball = load_external_features(self.folder)
        self.halves = self.spatial.half
        self.predictions = pd.DataFrame({"raw_label": "X", "state_entropy": 1.0},
                                        index=self.spatial.index)

    def response(self, start, end, label, confidence):
        return parse_arbiter_response(json.dumps({
            "start_frame": start, "end_frame": end, "override_label": label,
            "confidence": confidence,
        }), (200000, 200005), halves=self.halves)

    def test_adapter_uses_sample_pitch_and_frame_ids(self):
        self.assertEqual(self.spatial.index[0], 200000)
        self.assertAlmostEqual(self.spatial.ball_x.iloc[0], 52.5)
        self.assertAlmostEqual(self.spatial.dist_nearest_H.iloc[0], 1.05, places=5)
        self.assertAlmostEqual(self.spatial.dist_nearest_A.iloc[0], 42.0)

    def test_missing_gaps_reset_at_period_boundary(self):
        tracking_fixture(self.folder, missing_frames=(200005, 200006))
        spatial, deadball = load_external_features(self.folder)
        self.assertTrue(spatial.loc[200005:200006, "ball_x"].isna().all())
        self.assertTrue(spatial.loc[200005:200006, "gap_length_frames"].eq(1).all())
        self.assertTrue(deadball.loc[200005:200006, "is_dead_ball_prob"].eq(0.5).all())

    def test_mismatched_team_timelines_are_rejected(self):
        tracking_fixture(self.folder, away_offset=1)
        with self.assertRaisesRegex(ValueError, "disagree"):
            load_external_features(self.folder)

    def test_window_selection_uses_external_periods(self):
        self.assertEqual(find_windows(self.predictions, 0.9, halves=self.halves),
                         [(200000, 200005), (200006, 200011)])
        selected = select_windows(self.predictions, 0.9, 2, 4, halves=self.halves)
        self.assertEqual(selected, [(200000, 200003), (200006, 200009)])

    def test_accepted_external_response_preserves_competition_default(self):
        response = dict(start_frame=200000, end_frame=200002, override_label="H", confidence=0.9)
        with self.assertRaises(ValueError):
            parse_arbiter_response(json.dumps(response), (200000, 200002))
        result = local_arbiter(self.spatial, self.deadball, self.predictions,
                               (200000, 200002), halves=self.halves)
        self.assertEqual(result.override_label.tolist(), ["H"])
        labels = apply_overrides(self.predictions, result, 0.8)
        self.assertTrue(labels.loc[200000:200002].eq("H").all())
        self.assertEqual(labels.loc[200003], "X")

    def test_cross_period_and_out_of_domain_responses_are_rejected(self):
        for start, end in ((200005, 200006), (199999, 200000), (200010, 200012)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                parse_arbiter_response(json.dumps({"start_frame": start, "end_frame": end,
                    "override_label": "H", "confidence": 0.9}), (199999, 200012), halves=self.halves)

    def test_overlaps_follow_confidence_then_stable_input_order(self):
        home = self.response(200000, 200004, "H", 0.8)
        away = self.response(200002, 200005, "A", 0.95)
        rows = pd.concat([away, home], ignore_index=True)
        labels = apply_overrides(self.predictions, rows, 0.8)
        self.assertTrue(labels.loc[200000:200001].eq("H").all())
        self.assertTrue(labels.loc[200002:200005].eq("A").all())
        self.assertEqual(labels.loc[200006], "X")
        tie = self.response(200002, 200005, "D", 0.8)
        labels = apply_overrides(self.predictions, pd.concat([home, tie]), 0.8)
        self.assertTrue(labels.loc[200002:200005].eq("D").all())

    def test_below_threshold_is_filtered_and_exact_threshold_is_accepted(self):
        rejected = self.response(200000, 200001, "H", 0.79)
        accepted = self.response(200002, 200004, "A", 0.8)
        labels = apply_overrides(self.predictions, pd.concat([rejected, accepted]), 0.8)
        self.assertTrue(labels.loc[200000:200001].eq("X").all())
        self.assertTrue(labels.loc[200002:200004].eq("A").all())

    def test_external_cli_is_reproducible(self):
        config = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8-sig"))
        config["thresholds"]["entropy"] = 0.0
        config_path = self.folder / "config.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
        for name in ("first", "repeat"):
            subprocess.run([sys.executable, str(ROOT / "scripts/assess_external_arbiter.py"),
                            "--data-dir", str(self.folder), "--config", str(config_path),
                            "--out", str(self.folder / name)], check=True, cwd=ROOT,
                           capture_output=True, text=True)
        first = json.loads((self.folder / "first/summary.json").read_text())
        second = json.loads((self.folder / "repeat/summary.json").read_text())
        self.assertEqual(first, second)
        self.assertEqual(first["frames"], 12)
        self.assertEqual(first["windows_reviewed"], 2)
        labels = pd.read_csv(self.folder / "first/with_overrides.csv")
        np.testing.assert_array_equal(labels.frame, self.spatial.index)


if __name__ == "__main__":
    unittest.main()
