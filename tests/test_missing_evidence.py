from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from src.contracts import day1_mocks, frame_halves
from src import p2_deadball_detector as p2, p3_sequence_model as p3
from scripts import check_p1_loader


class MissingEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(Path('configs/config.yaml').read_text())
        cls.a, cls.b = day1_mocks()
        cls.start = int(np.flatnonzero(frame_halves() == 1)[0]) + 100

    def missing(self):
        a = self.a.copy()
        window = slice(self.start, self.start + 199)
        a.loc[window, ['ball_x', 'ball_y', 'ball_speed', 'ball_accel',
                       'dist_nearest_H', 'dist_nearest_A']] = np.nan
        a.loc[window, 'gap_length_frames'] = 200
        a.loc[window, 'ball_is_imputed'] = False
        return a, window

    def test_p2_missing_is_neutral_and_tag_is_weak_evidence(self):
        a, window = self.missing()
        event = {'code': 'SET PIECES', 'tags': {'Type': 'Free Kick'},
                 'start_frame': self.start, 'end_frame': self.start + 200}
        untagged = p2.build_mask(self.config, a, [])
        tagged = p2.build_mask(self.config, a, [event])
        np.testing.assert_allclose(untagged.loc[window, 'is_dead_ball_prob'], 1 / 3)
        np.testing.assert_allclose(tagged.loc[window, 'is_dead_ball_prob'], 0.5)
        self.assertAlmostEqual(float(tagged.loc[self.start + 200, 'is_dead_ball_prob']),
                               float(untagged.loc[self.start + 200, 'is_dead_ball_prob']))
        emissions, _ = p3.build_emissions(a.loc[window], untagged.loc[window], self.config)
        np.testing.assert_allclose(emissions, 1 / 3)

    def test_binary_ambiguity_abstains_for_both_decoders(self):
        a, window = self.missing()
        b = self.b.loc[window].copy()
        b['is_dead_ball_prob'] = 0.05
        for decoder in ('posterior', 'viterbi'):
            config = deepcopy(self.config)
            config['hmm']['decoder'] = decoder
            result = p3.run(config, a.loc[window], b)
            self.assertTrue(result.raw_label.eq('X').all())

    def test_missing_shield_preserves_strong_deadball(self):
        a, window = self.missing()
        b = self.b.loc[window].copy()
        b['is_dead_ball_prob'] = 0.98
        self.assertTrue(p3.run(self.config, a.loc[window], b).raw_label.eq('D').all())

    def test_tag_does_not_override_observed_live_motion(self):
        a = self.a.copy()
        window = slice(self.start, self.start + 199)
        a.loc[window, ['ball_x', 'ball_y']] = [50, 30]
        a.loc[window, 'ball_speed'] = 1
        a.loc[window, 'ball_is_imputed'] = False
        event = {'code': 'SET PIECES', 'tags': {'Type': 'Free Kick'},
                 'start_frame': self.start, 'end_frame': self.start + 200}
        b = p2.build_mask(self.config, a, [event])
        np.testing.assert_allclose(b.loc[window, 'is_dead_ball_prob'], 0.05)

    def test_stress_fixture_runs_actual_detector(self):
        from src.p3_synthetic import generate_with_detector
        from src.contracts import validate
        a, b, truth = generate_with_detector(self.config, seed=7)
        validate('spatial', a)
        validate('deadball', b)
        self.assertTrue((a.gap_length_frames > 100).any())
        self.assertTrue(np.isclose(b.is_dead_ball_prob, 1 / 3).any())
        self.assertEqual(len(truth), len(a))

    def test_integrated_tagged_occlusion_supports_deadball(self):
        a, window = self.missing()
        event = {'code': 'SET PIECES', 'tags': {'Type': 'Free Kick'},
                 'start_frame': self.start, 'end_frame': self.start + 200}
        b = p2.build_mask(self.config, a, [event])
        self.assertTrue(p3.run(self.config, a.loc[window], b.loc[window]).raw_label.eq('D').all())

    def test_failed_loader_checks_cannot_write_handoff(self):
        for real_failures, synthetic_failures in ((['alignment'], []), ([], ['fixture'])):
            with patch('sys.argv', ['check_p1_loader.py', '--write-a']), \
                 patch.object(check_p1_loader, 'real_tracking_report',
                              return_value=({}, real_failures, None)), \
                 patch.object(check_p1_loader, 'synthetic_report',
                              return_value=({}, synthetic_failures)), \
                 patch.object(check_p1_loader, 'write') as write:
                self.assertEqual(check_p1_loader.main(), 1)
                write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
