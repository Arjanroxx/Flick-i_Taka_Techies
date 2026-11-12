# P1 — A v1, quality pass on speeds and gaps (Nov 9 backlog, completed Nov 12)

Owner: P1. Nov 9 deliverable: inspect A v0 for unreasonable speeds, missing-team distances and
gap behavior; fix clear processing bugs; publish A v1 with a changelog from A v0.

## Findings and fixes

**1. Derivatives across filled frames (fixed).** A v0 computed `ball_vx/vy/speed/accel` from
differenced *filled* positions. An interpolated frame sitting between two tracker-teleport
readings (e.g. 37.9 m → 98.7 m in 3 frames at 25 fps) reported a 720 m/s "ball speed" — an
interpolated number masquerading as a measurement. Fix in `src/p1_spatial_features.py`:
velocity steps now require observed positions at both ends of the step. Frames inside an imputed
gap, and the first observed frame after one, report NaN speed/velocity/acceleration instead of
interpolation residue. Derivatives still never cross half boundaries.

**2. Interpolation across tracker teleports (fixed).** The short-gap fill happily connected
endpoints 86 m apart across a 2-frame hole (~180 m/s implied — impossible for a ball; p99 of
*observed* speeds is 24.6 m/s). The fill now requires the endpoint span to imply an average
speed under a 40 m/s ceiling; gaps above it stay missing. Rejected fills: 11 runs / 32 frames,
all implying >40 m/s on replay of the v0 rule (including the 112605–112606 teleport and a
~39 m span over a short gap).

| Metric | A v0 | A v1 |
|---|---|---|
| Rows / contract | 199,319 / pass | 199,319 / pass |
| Ball imputed (play blocks) | 51 frames | **19 frames** |
| Gaps filled (runs) | 15 | 4 |
| Ball speed p99.9 | 57.7 m/s | 54.6 m/s |
| Ball speed max | **720.65 m/s** | **109.6 m/s** |
| Frames over 100 m/s | 10 | 7 |
| `ball_accel` max | **18,095 m/s²** | **187.6 m/s²** |
| `rel_vel_nearest_H` max | 723.6 m/s | 108.9 m/s |

Remaining >100 m/s claims (7 frames, e.g. 179905–179911) are observed→observed tracker sweeps:
the ball re-enters at y = −5.98 m and crosses the pitch diagonally. The derivative is a faithful
reading of the delivered tracking, not a processing bug, so it is retained. Downstream, P2
rejects derivatives that depend on unobserved positions, and P3 treats imputed frames as neutral
evidence.

**3. Missing-team distances (reviewed, no change).** While the ball is observed, 184 frames in
play have no observed H slot (all 24 H track slots missing together, clustered at 90038–90221,
the end of half 1). A has 0 such frames. This is occlusion in the delivered tracking, not a
ticketing of slots to teams: `dist_nearest_* = NaN` there is the correct contract behaviour and
feeds P3's neutral-evidence rule (Finite normalized probabilities on unavailable distances).

**4. Gap behavior (reviewed, no change).** 150 gaps in play (median 268 frames ≈ 10.7 s, max
5,537). Only 16 are ≤ `short_gap` (12) and eligible for filling; 4 of those passed the new
speed ceiling and are filled (30631–30642, 43023–43024, 55408–55410, 68681–68682). Long and
edge gaps remain missing by design.

## Reproduce

```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a  # regenerate A v1
.venv/Scripts/python.exe -m unittest discover -s tests -v       # 27 tests
```

A v1 changes from A v0 are confined to `ball_x/y` on 32 frames, `ball_vx/vy/speed/accel` on
derivative steps touching filled positions, and `ball_is_imputed`/`gap_length_frames` recording.
Team-slot mapping, metre conversion and the official `half` export are unchanged.
