# P2 stoppage mask

## Generate handoff B

From the repository root, with your authorized tactical bundle and P1's validated
`artifacts/spatial_features.parquet`:

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py --deadball-only --data-dir 'D:/match-data'
```

The command writes `artifacts/deadball_mask.parquet`, validates the B contract,
and prints counts for observed boundary exits by frame, strong boundary evidence,
tagged frames by category, and restart candidates by category. Use the team's
`--config` option if A or B uses a different path. For P3 integration, use the same
config with `--from-artifacts --skip-evaluation`. The regular full run rebuilds
both A and B using the same detector.

Share the B file privately with P3. Record the P1 handoff version, this code commit
and the exact config with the handoff. Run the same command twice against the same
inputs to check reproducibility. For identical environments you can compare hashes
using `Get-FileHash artifacts/deadball_mask.parquet` after each run.

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
and stays after any earlier observed fast in-bounds motion within that lookback.
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
