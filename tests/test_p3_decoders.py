from pathlib import Path
import unittest

import numpy as np
import pandas as pd
import yaml

from src.contracts import day1_mocks, frame_halves
from src.p3_sequence_model import run, team_evidence


class P3DecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "configs/config.yaml").read_text()
        )
        cls.spatial, cls.deadball = day1_mocks()
        cls.predictions = run(cls.config, cls.spatial, cls.deadball)

    def test_viterbi_is_deterministic_and_valid(self):
        repeat = run(self.config, self.spatial, self.deadball)
        pd.testing.assert_frame_equal(self.predictions, repeat)
        self.assertEqual(self.config["hmm"]["decoder"], "viterbi")
        self.assertTrue(self.predictions.raw_label.isin(list("HADX")).all())

    def test_viterbi_ignores_the_other_half(self):
        halves = self.spatial.half.to_numpy()
        for target, other in ((1, 2), (2, 1)):
            with self.subTest(target_half=target):
                spatial = self.spatial.copy()
                deadball = self.deadball.copy()
                spatial.loc[halves == other, ["dist_nearest_H", "dist_nearest_A"]] = np.nan
                spatial.loc[halves == other, "gap_length_frames"] = 1
                deadball.loc[halves == other, "is_dead_ball_prob"] = 1.0
                perturbed = run(self.config, spatial, deadball)
                pd.testing.assert_series_equal(
                    perturbed.loc[halves == target, "raw_label"],
                    self.predictions.loc[halves == target, "raw_label"],
                )

    def test_unknown_decoder_is_rejected(self):
        config = dict(self.config)
        config["hmm"] = dict(self.config["hmm"], decoder="posterior_viterbi")
        with self.assertRaises(ValueError):
            run(config, self.spatial, self.deadball)

    def test_temperature_flattens_a_single_frame_emission(self):
        frame = self.spatial.index[self.spatial.half.to_numpy() == 1][0]
        spatial = self.spatial.loc[[frame]].copy()
        spatial.loc[frame, ["dist_nearest_H", "dist_nearest_A"]] = [1.0, 5.0]
        spatial.loc[frame, "ball_is_imputed"] = False
        sharp, _ = team_evidence(spatial, temperature=1.0)
        calm, _ = team_evidence(spatial, temperature=3.0)
        self.assertGreater(sharp[0, 0], calm[0, 0])
        self.assertGreater(calm[0, 0], calm[0, 1])

    def test_outside_play_stays_x_for_both_decoders(self):
        outside = frame_halves() == 0
        self.assertTrue((self.predictions.raw_label.to_numpy()[outside] == "X").all())


if __name__ == "__main__":
    unittest.main()
