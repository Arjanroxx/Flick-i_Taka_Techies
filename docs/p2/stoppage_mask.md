# P2 stoppage mask

## Generate handoff B

Use the team's frozen P1 handoff at `artifacts/spatial_features.parquet` and the
authorized tactical bundle. From a clean checkout of the candidate commit, run:

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
.venv/Scripts/python.exe scripts/run_full_pipeline.py --deadball-only --verify-deadball --data-dir 'D:/match-data' |
    Set-Content -Encoding utf8 artifacts/p2_handoff.json
```

Pass `--config` when the team uses different paths. The command validates B and
replaces the configured output after the repeat run produces the same SHA-256.
The JSON records the checkout commit, hashes of A, the XML and the config,
and the hash of B. It also records kickoff alignment, set-piece counts and
overlaps, example intervals, candidate restarts and missing-ball counts.
`--deadball-only` also works by itself for a single run.

Before signing off, check `reproduced_byte_for_byte`, both kickoff containment
checks, the tag counts against [DATA.md](../../DATA.md), and the reported A hash
against P1's frozen handoff. Use the interval examples and restart counts to
investigate deviations in the automatic evidence. A match can reproduce exactly
while still containing missed or false stoppages.

Share B and the JSON privately with P3, together with P1's version and the config
used. P3 can replay the same A/B pair with `--from-artifacts --skip-evaluation`.
The regular full run builds A and B with the same detector. Keep the XML,
Parquet files and match-specific JSON out of Git.

## How B is built

The official XML loader converts seconds to tactical video frames at 25 fps and
rounds to the nearest frame. Each tag includes its start and excludes its end.
P2 intersects these windows with the official halves and recognizes throw-ins,
corners, goal kicks, free kicks, kick-offs, penalties and fouls in the set-piece
category. The team tag is irrelevant to dead-ball evidence, so `N/A` is accepted.

P1 supplies unclipped ball positions in metres, speed, acceleration and an
imputation flag. P2 uses the official pitch dimensions and only observed
coordinates for its boundary flag. Strong boundary evidence requires at least
three consecutive observed positions outside the pitch, with at least one
position over 0.35 m beyond an edge. Missing or interpolated positions break that
run. P2 also rejects speed or acceleration that depends on unobserved positions.

Inside a tagged window, the first supported restart candidate is the first
frame of sustained in-bounds motion of at least 3 m/s for three frames. That
motion must follow a confirmed outside run or recent observed stillness
(at or below 0.3 m/s for three frames) and an acceleration of at least 8 m/s²
for the stillness case. A supported lead-up can extend back up to three seconds
inside the tag. It starts at observed stillness or a confirmed boundary exit
and stays after any earlier observed in-bounds movement above the stationary
threshold within that lookback.
Overlapping tags combine evidence by strength. The narrower tag supplies the
display category unless the frame is a restart, in which case the selected
restart's tag supplies it.

| Probability | Evidence |
| --- | --- |
| 1.00 | Outside the published play blocks |
| 0.98 | Confirmed observed boundary exit |
| 0.70 | Supported lead-up to a restart in a tagged window |
| 0.60 | Sustained observed stillness in a tagged window without a detected restart |
| 0.05 | Default when stronger evidence is absent, including the detected restart frame |

B has one row for every tactical video frame and four columns. `is_dead_ball_prob`
feeds P3's HMM as its dead-ball emission. `is_out_of_bounds` records observed
positions strictly outside the rectangle, even if a run is too short to receive
0.98. `active_set_piece_type` records the tag category and `restart_frame_flag`
marks the inferred restart. The last three columns are diagnostic in the current
P3 decoder. P3 still decides the final sequence from the probability and other
emissions, and exports `X` outside the official play blocks.

## Verification and limits

Run `python -m unittest discover -s tests -v`. The P2 tests cover XML rounding,
exclusive ends, tag categories, overlap order, tracking jitter, observed exits,
restart spikes, imputed derivatives, and separation between halves.

The thresholds are provisional. An untagged in-bounds stoppage, an occluded
restart, or a projected airborne ball can still be misread. The probabilities
are heuristic evidence weights. Verify tag counts, inferred restarts and
reproducibility locally against the delivered assets before freezing B. Use the
public five-minute labels only to sanity-check alignment and output, and use
eligible other-match labels for model selection.

## Candidate verification

Synthetic fixtures exercise a one-frame tracking spike, a sustained observed
boundary exit, a restart after stillness, missing and imputed ball positions,
and slow live motion between two stationary intervals. The sustained-motion
rule rejects the isolated spike, and the backfill stops at slow live motion.
The fixture with a supported throw-in retains the restart on the first in-bounds
frame of the sustained return. These checks support retaining the existing
three-frame confirmation, 0.35 m boundary margin and 3 m/s restart threshold
for this candidate. They do not measure generalization to a second match.

The end-to-end fixture derives A using the merged P1 feature builder, reads a
synthetic tactical XML, reproduces B byte for byte and feeds A/B to P3 and the
official CSV validator. Real-match B and final sign-off require the authorized
XML and a confirmed frozen A. The public five-minute labels are reserved for
sanity checks and were not used to set the thresholds.
