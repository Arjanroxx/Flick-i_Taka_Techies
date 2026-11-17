from copy import deepcopy
import itertools
import unittest

import numpy as np
import pandas as pd

from src.contact_transitions import transition_schedule
from src.p3_sequence_model import build_emissions, forward_backward, viterbi, run


class ContactTransitionTests(unittest.TestCase):
    def setUp(self):
        self.t = np.array([[.999, .0004, .0006], [.0004, .999, .0006], [.0005, .0005, .999]])
        self.a = pd.DataFrame({'half': 1, 'ball_x': 50., 'ball_y': 30.,
            'dist_nearest_H': [1.] * 6 + [5.] * 6,
            'dist_nearest_A': [5.] * 6 + [1.] * 6,
            'ball_is_imputed': False, 'gap_length_frames': 0}, index=pd.Index(range(12), name='frame'))
        self.b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=self.a.index)
        self.config = {'hmm': {'team_evidence': 'sustained_control', 'emission_temperature': 3.,
            'contact_switch_probability': .1, 'transition': self.t, 'decoder': 'viterbi'},
            'control': {}, 'thresholds': {'entropy': .9, 'short_gap': 12}}

    def schedule(self):
        return transition_schedule(self.a, self.b, self.t, self.config)

    def test_only_confirmed_turnover_entry_changes_and_D_unchanged(self):
        schedule = self.schedule()
        changed = np.any(schedule != self.t, axis=(1, 2))
        np.testing.assert_array_equal(np.flatnonzero(changed), [6])
        self.assertEqual(schedule[6, 0, 1], .1)
        np.testing.assert_array_equal(schedule[:, :, 2], np.broadcast_to(self.t[:, 2], (12, 3)))
        np.testing.assert_array_equal(schedule[:, 2, :], np.broadcast_to(self.t[2, :], (12, 3)))
        np.testing.assert_allclose(schedule.sum(axis=2), 1)
        self.assertTrue((schedule >= 0).all())

    def test_brief_touch_missing_imputation_and_deadball_cannot_propose(self):
        for kind in ('brief', 'missing', 'imputed', 'dead'):
            a, b = self.a.copy(), self.b.copy()
            if kind == 'brief':
                a.loc[8:, ['dist_nearest_H', 'dist_nearest_A']] = [1., 5.]
            elif kind == 'missing':
                a.loc[6:, 'ball_x'] = np.nan
            elif kind == 'imputed':
                a.loc[6:, 'ball_is_imputed'] = True
            else:
                b.loc[6:, 'is_dead_ball_prob'] = .9
            schedule = transition_schedule(a, b, self.t, self.config)
            np.testing.assert_array_equal(schedule, np.broadcast_to(self.t, schedule.shape))

    def test_half_frame_gap_and_confirmed_D_reset_history(self):
        for kind in ('half', 'gap', 'dead'):
            a, b = self.a.copy(), self.b.copy()
            if kind == 'half':
                a.loc[6:, 'half'] = 2
            elif kind == 'gap':
                a.index = b.index = pd.Index([0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], name='frame')
            else:
                b.loc[5, 'is_dead_ball_prob'] = .9
            schedule = transition_schedule(a, b, self.t, self.config)
            np.testing.assert_array_equal(schedule, np.broadcast_to(self.t, schedule.shape))

    def test_team_swap_equivariance(self):
        original = self.schedule()
        self.a[['dist_nearest_H', 'dist_nearest_A']] = self.a[['dist_nearest_A', 'dist_nearest_H']].to_numpy()
        swapped = self.schedule()
        np.testing.assert_array_equal(swapped, original[:, [1, 0, 2], :][:, :, [1, 0, 2]])

    def test_time_varying_inference_matches_exhaustive_paths(self):
        emissions = np.array([[.57, .32, .11], [.21, .68, .11], [.12, .19, .69], [.68, .21, .11]])
        schedule = np.tile(self.t, (4, 1, 1))
        schedule[1] = [[.6, .3, .1], [.1, .8, .1], [.2, .1, .7]]
        schedule[2] = [[.7, .2, .1], [.3, .4, .3], [.1, .1, .8]]
        paths = list(itertools.product(range(3), repeat=4))
        weights = []
        posterior = np.zeros((4, 3))
        for path in paths:
            weight = emissions[0, path[0]] / 3
            for index in range(1, 4):
                weight *= schedule[index, path[index-1], path[index]] * emissions[index, path[index]]
            weights.append(weight)
            for index, state in enumerate(path):
                posterior[index, state] += weight
        posterior /= sum(weights)
        np.testing.assert_allclose(forward_backward(emissions, np.ones(4), schedule), posterior)
        np.testing.assert_array_equal(viterbi(emissions, np.ones(4), schedule),
            np.array(list('HAD'))[list(paths[int(np.argmax(weights))])])
        constant = np.tile(self.t, (4, 1, 1))
        np.testing.assert_array_equal(forward_backward(emissions, np.ones(4), constant),
                                      forward_backward(emissions, np.ones(4), self.t))
        np.testing.assert_array_equal(viterbi(emissions, np.ones(4), constant),
                                      viterbi(emissions, np.ones(4), self.t))

    def test_invalid_probability_or_other_mode_fails(self):
        for value in (-.1, 0, .5, np.nan):
            self.config['hmm']['contact_switch_probability'] = value
            with self.assertRaises(ValueError):
                self.schedule()
        self.config['hmm'].update(contact_switch_probability=.1, team_evidence='distance')
        with self.assertRaises(ValueError):
            self.schedule()

    def test_recovers_supported_short_possession_without_changing_emissions(self):
        a = pd.concat([self.a.iloc[:1]] * 66, ignore_index=True)
        a.index.name = 'frame'
        a.loc[30:35, ['dist_nearest_H', 'dist_nearest_A']] = [5., 1.]
        b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=a.index)
        old = deepcopy(self.config)
        del old['hmm']['contact_switch_probability']
        before, after = build_emissions(a, b, old), build_emissions(a, b, self.config)
        np.testing.assert_array_equal(before[0], after[0])
        np.testing.assert_array_equal(before[1], after[1])
        self.assertTrue(run(old, a, b).raw_label.eq('H').all())
        result = run(self.config, a, b)
        self.assertTrue(result.raw_label.iloc[30:36].eq('A').all())
        self.assertTrue(result.raw_label.iloc[:30].eq('H').all())
        self.assertTrue(result.raw_label.iloc[36:].eq('H').all())

    def test_scheduled_inference_resets_halves_and_keeps_outside_X(self):
        e = np.array([[.8, .1, .1], [.1, .8, .1], [.1, .1, .8], [.2, .7, .1]])
        halves = np.array([1, 1, 0, 2])
        schedule = np.tile(self.t, (4, 1, 1))
        together = forward_backward(e, halves, schedule)
        np.testing.assert_allclose(together[:2], forward_backward(e[:2], halves[:2], schedule[:2]))
        np.testing.assert_array_equal(together[2], [0, 0, 1])
        np.testing.assert_allclose(together[3], e[3])
        self.assertEqual(viterbi(e, halves, schedule)[2], 'X')


if __name__ == '__main__':
    unittest.main()
