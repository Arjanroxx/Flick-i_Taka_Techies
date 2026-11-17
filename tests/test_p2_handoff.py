import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import yaml

from games import GAME, GAMES, asset_paths
from scripts.p2_handoff import sha256
from src.contracts import FRAME_COUNT, read, write
from src.p1_spatial_features import build_features
from starter.load_smart_tagging import KICKOFF_VIDEO_FRAMES

ROOT = Path(__file__).resolve().parents[1]


class P2HandoffTests(unittest.TestCase):
    def test_p1_tracking_xml_to_reproducible_b(self):
        config = yaml.safe_load((ROOT / "configs/config.yaml").read_text())
        fps = GAMES[GAME]["fps"]
        frame = KICKOFF_VIDEO_FRAMES["1st Half"] + 100
        ball = np.full((FRAME_COUNT, 2), np.nan, dtype="float32")
        ball[frame:frame + 7, 0] = [-1, -1, -1, 0.2, 0.4, 0.6, 0.8]
        ball[frame:frame + 7, 1] = 30
        players = np.full((FRAME_COUNT, 2, 3), np.nan, dtype="float32")
        spatial = build_features(ball, players, np.array([0, 1]), config["thresholds"]["short_gap"])

        def instance(piece, start, stop, half="1st Half"):
            return (
                f"<instance><start>{start / fps}</start><end>{stop / fps}</end>"
                "<code>SET PIECES</code>"
                f"<label><group>Type</group><text>{piece}</text></label>"
                f"<label><group>Half</group><text>{half}</text></label>"
                "<label><group>Team</group><text>N/A</text></label></instance>"
            )

        with TemporaryDirectory() as directory:
            folder = Path(directory)
            spatial_path = folder / "a.parquet"
            output = folder / "b.parquet"
            config_path = folder / "config.yaml"
            config["paths"].update(spatial=str(spatial_path), deadball=str(output))
            for name in ("predictions", "overrides", "submission"):
                config["paths"][name] = str(folder / Path(config["paths"][name]).name)
            config_path.write_text(yaml.safe_dump(config))
            write("spatial", spatial, spatial_path)
            xml = Path(asset_paths(data_dir=folder)["smart_tagging"])
            xml.parent.mkdir()
            kickoffs = "".join(instance("Kick Off (Start)", start - 5, start + 5, half)
                               for half, start in KICKOFF_VIDEO_FRAMES.items())
            xml.write_text("<root>" + kickoffs + instance("Throw-in", frame, frame + 7)
                           + instance("Corner Kick", frame + 1, frame + 2) + "</root>")
            report = json.loads(subprocess.check_output([
                sys.executable, str(ROOT / "scripts/run_full_pipeline.py"),
                "--deadball-only", "--verify-deadball", "--config", str(config_path),
                "--data-dir", str(folder),
            ], cwd=ROOT))
            mask = read("deadball", output)
            self.assertEqual(report["inputs_sha256"]["spatial"], sha256(spatial_path))
            self.assertEqual(report["deadball_sha256"], sha256(output))
            self.assertTrue(report["reproduced_byte_for_byte"])
            self.assertTrue(report["kickoff_time_base"]["agrees"])
            self.assertEqual(report["set_piece_tags_by_type"],
                             {"kick_off": 2, "throw_in": 1, "corner": 1})
            self.assertEqual(report["windows_overlapping_earlier_window_by_type"], {"corner": 1})
            self.assertEqual(report["windows_with_matching_restart_by_type"], {"throw_in": 1})
            self.assertEqual(mask.index[mask.restart_frame_flag].tolist(), [frame + 3])
            self.assertEqual(report["strong_boundary_frames"], 3)
            replay = subprocess.check_output([
                sys.executable, str(ROOT / "scripts/run_full_pipeline.py"),
                "--from-artifacts", "--skip-evaluation", "--config", str(config_path),
            ], cwd=ROOT, text=True)
            self.assertIn(f"{FRAME_COUNT} rows", replay)
            self.assertIn("Valid.", replay)
