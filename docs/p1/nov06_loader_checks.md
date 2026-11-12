# P1 — Nov 6 loader checks (backlog completed Nov 12)

Owner: P1. Data-arrival review of the delivered tactical tracking, plus synthetic
missing-observation cases, as specified in [TEAM_ROADMAP.md](../../TEAM_ROADMAP.md) for Nov 6.
Completed Nov 12, 2026 together with the rest of the outstanding P1 preparation backlog.

## How to reproduce

```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py           # checks only
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a  # also regenerate handoff A
```

The script prints a JSON report, exits non-zero on any failure, and with `--write-a`
regenerates `artifacts/spatial_features.parquet` from the tactical bundle. The saved report
from this run is `artifacts/p1/nov06_loader_checks.json` (local, not committed).

## Results — real tactical tracking

| Check | Outcome |
|---|---|
| ATD alignment | **Pass** — 199,319 records, `frame_id` 1..199319 contiguous, `video_frame = frame_id - 1`, first record maps to video frame 0 |
| Team-slot mapping | **Pass** — 46 slots from the metadata: 24 H (Barcelona), 22 A (Athletic), no empty team |
| Ball missingness | 43.06% of all frames; **40.69% inside the published play blocks** (matches the ~41% in DATA.md); half 1: 40.65%, half 2: 40.73%; 21,188 missing frames outside play |
| Player missingness | 58.75% of all frames, 55.46% inside play blocks |
| Metre conversion | Medians plausible: ball (55.77, 39.78) m, players (53.08, 35.74) m on a 105.3 × 68 m pitch |
| Out-of-bounds | 2.486% of observed in-play ball positions lie outside the pitch rectangle; extremes ball x [-6.86, 117.29], y [-7.28, 101.22]. Preserved unclipped for P2's boundary evidence |
| Sanity bounds | Range within pitch ±50% and medians on-pitch — catches scale/axis mistakes while tolerating tracker drift |

## Results — synthetic missing-observation cases

All 14 checks pass through `build_features` + `validate("spatial")`:

- Short gap (5 frames ≤ `short_gap`=12) inside a half: linearly interpolated, `ball_is_imputed`
  set, `gap_length_frames=5`.
- Long gap (50 frames): stays NaN, never imputed, length recorded.
- Edge gap at a half's first frames and gap touching a half's last frames: never interpolated —
  nothing can bridge into halftime or out of a half's boundary.
- Frames outside the play blocks: `half=0` and no ball coordinates.
- `ball_is_imputed` implies both coordinates present (contract rule), `half` matches the official
  blocks, first frame of each half has NaN `ball_speed` (no cross-half derivative).
- Ball missing: `dist_nearest_*` NaN and `local_density_*_3m` zero.
- Metre coordinates preserved on intact frames; an out-of-bounds fixture position (-3, 71) is
  passed through unclipped.

## Notes for the team

- The real baseline A was regenerated with this code: `artifacts/spatial_features.parquet`
  (199,319 rows, contract valid). This is the pre-review baseline; the reviewed A v0 follows in
  `docs/p1/nov08_a_v0.md`.
- Ball and player observation rates are similar across halves, so no half-specific loader
  handling is needed.
- Extreme out-of-bounds ball values (y up to 101 m) are tracker drift, not a scaling bug; they
  stay in A deliberately. Their effect on distances is reviewed in the Nov 9–11 quality pass.
