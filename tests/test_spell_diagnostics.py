import unittest

import numpy as np
import pandas as pd

from evaluation import possession_metrics as pm
from src.spell_diagnostics import diagnose


class SpellDiagnosticTests(unittest.TestCase):
    def diagnose(self, gt, pred, periods=None, **kwargs):
        index = pd.Index(range(100, 100+len(gt)), name='frame')
        return diagnose(pd.Series(list(gt), index=index), pd.Series(list(pred), index=index),
            pd.Series(periods if periods is not None else [1]*len(gt), index=index), 10, **kwargs)

    def test_missed_stoppage_bridges_two_same_team_spells(self):
        gt, pred = 'H'*10 + 'D'*4 + 'H'*10, 'H'*24
        summary, tables = self.diagnose(gt, pred)
        self.assertEqual(summary['merge_bridge_categories'], {'merged_across_stoppage': 1})
        self.assertEqual(summary['stoppage_categories'], {'missed': 1})
        self.assertEqual(summary['reference_spells'], 2)
        self.assertEqual(tables['merge_bridges'].iloc[0].start_frame, 110)
        self.assertEqual(tables['merge_bridges'].iloc[0].stop_frame_exclusive, 114)
        self.assertAlmostEqual(summary['spellF1'], pm.spell_scores(pm.label_codes(gt),
            pm.label_codes(pred), [(0, 24)])['mean_f1'])

    def test_missed_opponent_possession_is_not_a_deadball_error(self):
        summary, _ = self.diagnose('H'*10+'A'*4+'H'*10, 'H'*24)
        self.assertEqual(summary['merge_bridge_categories'], {'merged_across_opponent_possession': 1})
        self.assertEqual(summary['reference_spell_categories']['missed_team_possession'], 1)
        self.assertEqual(summary['stoppage_categories'], {})

    def test_correct_sequence_shifted_boundary_keeps_signed_errors(self):
        summary, tables = self.diagnose('H'*10+'A'*10, 'H'*12+'A'*8)
        self.assertEqual(summary['reference_spell_categories'], {'matched': 2})
        self.assertEqual(summary['merge_bridge_categories'], {})
        self.assertEqual(tables['reference_spells'].iloc[0].candidate_end_error_seconds, .2)
        self.assertEqual(tables['reference_spells'].iloc[1].candidate_start_error_seconds, .2)
        self.assertAlmostEqual(summary['matched_spell_internal_endpoint_errors']['mean_absolute_seconds'], .2)

    def test_boundary_mismatch_and_false_dead_remain_separate(self):
        summary, _ = self.diagnose('H'*10+'A'*10, 'H'*18+'A'*2)
        self.assertEqual(summary['reference_spell_categories']['boundary_or_duration_mismatch'], 1)
        summary, _ = self.diagnose('H'*10, 'D'*10)
        self.assertEqual(summary['reference_spell_categories'], {'predicted_dead_instead_of_possession': 1})

    def test_unknown_reference_and_half_boundaries_never_create_bridge(self):
        for gt, periods in [('HHXXHH', [1]*6), ('HHHH', [1, 1, 2, 2])]:
            summary, _ = self.diagnose(gt, 'H'*len(gt), periods)
            self.assertEqual(summary['merge_bridge_categories'], {})
            self.assertEqual(summary['reference_spells'], 2)
            self.assertEqual(summary['spellF1'], 1.)

    def test_X_fill_matches_official_and_resets_per_reference_run(self):
        gt, pred = 'HHAA'+'XX'+'AAAA', 'HHXX'+'XX'+'XXXA'
        summary, _ = self.diagnose(gt, pred)
        g, p = pm.label_codes(gt), pm.label_codes(pred)
        runs = pm.valid_runs(g)
        self.assertEqual(summary['spellF1'], pm.spell_scores(g, pm.fill_abstentions(p, runs), runs)['mean_f1'])
        self.assertEqual(summary['reference_spell_categories']['missed_team_possession'], 1)
        summary, _ = self.diagnose('HH', 'XX')
        self.assertEqual(summary['reference_spell_categories'], {'unanswered_reference_run': 1})

    def test_partial_D_coverage_and_HA_only_reference(self):
        summary, _ = self.diagnose('HHDDDDHH', 'HHDDHHHH')
        self.assertEqual(summary['stoppage_categories'], {'partly_covered': 1})
        summary, tables = self.diagnose('HHXXAA', 'HHXXAA', dead_reference_available=False)
        self.assertIsNone(summary['stoppage_categories'])
        self.assertFalse(summary['dead_reference_available'])
        self.assertIn('category', tables['stoppages'].columns)
        with self.assertRaises(ValueError):
            self.diagnose('HHDD', 'HHDD', dead_reference_available=False)

    def test_matching_totals_include_false_positive_fragments(self):
        gt, pred = 'H'*20, 'H'*8+'A'*4+'H'*8
        summary, tables = self.diagnose(gt, pred)
        self.assertEqual(summary['reference_spell_categories'], {'fragmented_or_boundary_mismatch': 1})
        at_half = summary['per_iou'][.5]
        self.assertEqual(at_half['n_matched']+at_half['n_missed'], summary['reference_spells'])
        self.assertEqual(at_half['n_matched']+at_half['n_spurious'], len(tables['predicted_spells']))
        self.assertEqual(sum(summary['reference_spell_categories'].values()), summary['reference_spells'])

    def test_alignment_invalid_labels_and_input_preservation(self):
        gt = pd.Series(list('HHAA'), index=pd.Index(range(4), name='frame'))
        pred, half = gt.copy(), pd.Series(1, index=gt.index)
        saved = pred.copy(deep=True)
        diagnose(gt, pred, half, 25)
        pd.testing.assert_series_equal(pred, saved)
        with self.assertRaises(ValueError):
            diagnose(gt, pred.set_axis(range(1, 5)), half, 25)
        with self.assertRaises(ValueError):
            diagnose(gt, pred.replace('A', 'Q'), half, 25)
        with self.assertRaises(ValueError):
            diagnose(gt, pred, half, np.nan)
        with self.assertRaises(ValueError):
            diagnose(gt, pred, half*0, 25)

    def test_mixed_separator_and_stoppage_without_same_team_bridge(self):
        summary, _ = self.diagnose('H'*8+'ADDD'+'H'*8, 'H'*20)
        self.assertEqual(summary['merge_bridge_categories'], {'merged_across_mixed_separator': 1})
        summary, _ = self.diagnose('HHDDDDAA', 'HHHHHHAA')
        self.assertEqual(summary['stoppage_categories'], {'missed': 1})
        self.assertEqual(summary['merge_bridge_categories'], {})

    def test_unknown_only_and_support_masks(self):
        summary, tables = self.diagnose('XXXX', 'HHAA')
        self.assertEqual(summary['scored_frames'], 0)
        self.assertEqual(summary['reference_spells'], 0)
        self.assertEqual(summary['spellF1'], 0)
        self.assertIn('candidate_start_error_seconds', tables['reference_spells'].columns)
        index = pd.Index(range(100, 104), name='frame')
        support = pd.Series(list('AXXX'), index=index)
        summary, tables = self.diagnose('AAAA', 'HHHH', control_support=support,
                                        ball_observed=pd.Series(True, index=index))
        self.assertEqual(summary['unmatched_spells_with_control_support'], 1)
        self.assertEqual(tables['reference_spells'].iloc[0].observed_ball_fraction, 1.)


if __name__ == '__main__':
    unittest.main()
