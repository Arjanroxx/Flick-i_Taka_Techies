"""Opt-in H/A switching opportunities at confirmed original-control turnovers."""
import numpy as np

from .control_evidence import sustained_control_evidence


def transition_schedule(spatial, deadball, transition, config):
    probability = config['hmm']['contact_switch_probability']
    if (not np.isfinite(probability) or not 0 < probability < .5
            or config['hmm'].get('team_evidence') != 'sustained_control'):
        raise ValueError('Contact switching requires sustained control and probability in (0, .5)')
    teams, known = sustained_control_evidence(spatial, deadball,
        config['hmm'].get('emission_temperature', 1.), config.get('control', {}))
    preference = np.where(known, teams.argmax(axis=1), -1)
    schedule = np.broadcast_to(transition, (len(spatial), 3, 3)).copy()
    frames, halves = spatial.index.to_numpy(), spatial.half.to_numpy()
    minimum = config['hmm'].get('contact_minimum_seconds', 0.)
    fps = config['hmm'].get('contact_fps', 25.)
    if not np.isfinite([minimum, fps]).all() or minimum < 0 or fps <= 0:
        raise ValueError('Invalid contact duration or frame rate')
    if minimum > 0 and len(preference):
        edges = np.r_[0, np.flatnonzero((preference[1:] != preference[:-1])
            | (halves[1:] != halves[:-1]) | (np.diff(frames) != 1)) + 1, len(preference)]
        for start, stop in zip(edges[:-1], edges[1:]):
            if stop-start < max(2, int(np.ceil(minimum*fps))):
                preference[start:stop] = -1
        # Only the transition proposal is filtered. Existing ownership emissions
        # and their original confirmation mask are never modified.
    last = -1
    for index, team in enumerate(preference):
        if (index == 0 or halves[index] != halves[index-1]
                or frames[index] != frames[index-1] + 1 or halves[index] == 0
                or deadball.is_dead_ball_prob.iloc[index] >= .5):
            last = -1
        if team < 0:
            continue
        if last >= 0 and team != last:
            # Transition at index means state[index-1] -> state[index]. Only
            # the opposite-team row changes. D entries remain exactly intact.
            source = 1 - team
            target = max(probability, transition[source, team])
            delta = target - transition[source, team]
            if delta > transition[source, source]:
                raise ValueError('Contact switch probability exceeds available self-transition mass')
            schedule[index, source, team] = target
            schedule[index, source, source] -= delta
        last = team
    return schedule
