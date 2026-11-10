from pathlib import Path
import tempfile
import unittest

import numpy as np
import yaml

from games import GAME, GAMES, asset_paths, half_video_blocks
from src.contracts import day1_mocks, validate
from src.p2_deadball_detector import build_mask, run


class DeadballDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "configs/config.yaml").read_text()
        )
        cls.template, _ = day1_mocks()
        cls.template["ball_is_imputed"] = False
        cls.template["ball_speed"] = np.float32(1)
        (_, cls.first, cls.last), (_, cls.second, _) = half_video_blocks(GAME)

    def setUp(self):
        self.spatial = self.template.copy()
        self.start = self.first + 100

    def event(self, piece, start=None, stop=None):
        return {
            "code": " SET PIECES ", "tags": {"tYpE": piece, "Team": "N/A"},
            "start_frame": self.start if start is None else start,
            "end_frame": self.start + 15 if stop is None else stop,
        }

    def burst(self, frame, count=3):
        self.spatial.loc[frame:frame + count - 1, "ball_speed"] = 4
        self.spatial.loc[frame, "ball_accel"] = 12

    def mask(self, *events):
        return validate("deadball", build_mask(self.config, self.spatial, events))

    def test_tag_loader_rounding_exclusive_end_and_categories(self):
        fps = GAMES[GAME]["fps"]
        names = ["Throw-in", "Corner Kick", "Goal Kick", "Free Kick",
                 "Kick Off (Start)", "Kick Off (After Goal)", "Penalty", "Foul", "Unknown"]
        expected = ["throw_in", "corner", "goal_kick", "free_kick",
                    "kick_off", "kick_off", "penalty", "foul", "none"]
        with tempfile.TemporaryDirectory() as data_dir:
            path = Path(asset_paths(data_dir=data_dir)["smart_tagging"])
            path.parent.mkdir(parents=True)
            instances = []
            for index, name in enumerate(names):
                frame = self.start + index * 4
                instances.append(
                    f"<instance><start>{(frame + 0.4) / fps}</start>"
                    f"<end>{(frame + 1.6) / fps}</end><code>SET PIECES</code>"
                    f"<label><group>Type</group><text>{name}</text></label>"
                    "<label><group>Team</group><text>N/A</text></label></instance>"
                )
            path.write_text("<root>" + "".join(instances) + "</root>", encoding="utf-8")
            config = self.config | {"data": self.config["data"] | {"directory": data_dir}}
            mask = validate("deadball", run(config, self.spatial))
        for index, piece in enumerate(expected):
            frame = self.start + index * 4
            self.assertEqual(mask.loc[frame:frame + 2, "active_set_piece_type"].tolist(),
                             [piece, piece, "none"])
        self.assertFalse(mask.restart_frame_flag.any())

    def test_sustained_exit_and_return(self):
        frame = self.start + 5
        self.spatial.loc[frame - 3:frame - 1, "ball_x"] = -1
        self.burst(frame)
        mask = self.mask(self.event("Throw-in"))
        self.assertTrue(mask.loc[frame - 3:frame - 1, "is_out_of_bounds"].all())
        np.testing.assert_allclose(mask.loc[frame - 3:frame - 1, "is_dead_ball_prob"], 0.98)
        self.assertEqual(mask.index[mask.restart_frame_flag].tolist(), [frame])
        self.assertAlmostEqual(mask.at[frame, "is_dead_ball_prob"], 0.05)

    def test_imputed_missing_and_boundary_jitter_are_not_strong_stoppages(self):
        frame = self.start
        self.spatial.loc[frame:frame + 4, "ball_x"] = [-1, -1, np.nan, -0.1, -0.1]
        self.spatial.at[frame + 1, "ball_is_imputed"] = True
        mask = self.mask()
        self.assertEqual(mask.loc[frame:frame + 4, "is_out_of_bounds"].tolist(),
                         [True, False, False, True, True])
        np.testing.assert_allclose(mask.loc[frame:frame + 4, "is_dead_ball_prob"], 0.05)

    def test_stationary_restart_and_overlap_order(self):
        frame = self.start + 6
        self.spatial.loc[frame - 3:frame - 1, "ball_speed"] = 0
        self.burst(frame)
        kick = self.event("Free Kick")
        short = self.event("Corner Kick", frame - 3, frame)
        mask = self.mask(kick, short)
        self.assertEqual(mask.index[mask.restart_frame_flag].tolist(), [frame])
        self.assertEqual(mask.at[frame, "active_set_piece_type"], "free_kick")
        self.assertEqual(mask.at[frame - 1, "active_set_piece_type"], "corner")
        self.assertAlmostEqual(mask.at[frame - 1, "is_dead_ball_prob"], 0.7)
        self.assertTrue(mask.equals(self.mask(short, kick)))

    def test_spike_needs_confirmed_motion_and_observed_derivatives(self):
        frame = self.start + 6
        self.spatial.loc[frame - 3:frame - 1, "ball_speed"] = 0
        self.burst(frame, count=1)
        event = self.event("Goal Kick")
        mask = self.mask(event)
        self.assertFalse(mask.restart_frame_flag.any())
        self.assertAlmostEqual(mask.at[frame - 1, "is_dead_ball_prob"], 0.6)
        self.burst(frame)
        self.spatial.at[frame - 2, "ball_is_imputed"] = True
        self.assertFalse(self.mask(event).restart_frame_flag.any())

    def test_motion_or_stillness_alone_does_not_create_a_restart(self):
        self.burst(self.start + 6)
        self.assertFalse(self.mask(self.event("Free Kick")).restart_frame_flag.any())
        self.spatial.loc[self.start:self.start + 5, "ball_speed"] = 0
        mask = self.mask()
        self.assertFalse(mask.restart_frame_flag.any())
        self.assertAlmostEqual(mask.at[self.start + 4, "is_dead_ball_prob"], 0.05)

    def test_evidence_resets_between_halves(self):
        self.spatial.loc[self.last - 2:self.last, "ball_x"] = -1
        self.burst(self.second)
        event = self.event("Corner Kick", self.last - 2, self.second + 3)
        mask = self.mask(event)
        self.assertFalse(mask.restart_frame_flag.any())
        self.assertEqual(mask.at[self.last + 1, "active_set_piece_type"], "none")
        self.assertEqual(mask.at[self.last + 1, "is_dead_ball_prob"], 1)
        self.assertAlmostEqual(mask.at[self.second, "is_dead_ball_prob"], 0.05)


if __name__ == "__main__":
    unittest.main()
