# P1 — A v0, the reviewed spatial baseline (Nov 8 backlog, completed Nov 12)

Owner: P1. The roadmap's Nov 8 deliverable: review the real spatial baseline, verify team-slot
mapping, metre conversion and missing-ball quality, and publish A v0 at the agreed handoff path.

## Handoff A v0

| | |
|---|---|
| File | `artifacts/spatial_features.parquet` (generated locally, kept out of Git) |
| Command | `.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a` |
| Rows | 199,319 (one per tactical video frame) |
| Contract | `validate("spatial", table)` passes — schema, dtypes, bounds, official `half` blocks, imputed-position rule |
| Code | `src/p1_spatial_features.py` at the commit recorded with this document |
| Inputs | tactical bundle in `data/tactical/` (BAR-ATH, delivered Nov 6) |

Share the parquet with P2/P3 through the agreed private location and record this version,
the commit and the config (`configs/config.yaml`, `short_gap: 12`) with the handoff.

## Verification results

**Team-slot mapping.** The ATD metadata assigns 46 track slots: 24 to H (Barcelona), 22 to A
(Athletic), read by `team_of_each_track` with the first `Team` element as home (FIFA/EPTS
convention, stated independently by DATA.md). No empty team; the loader check fails if either
side has zero slots.

**Metre conversion.** Normalised 0–1 tracking is scaled by the official 105.3 × 68 m pitch.
Coordinate medians sit on-pitch: ball (55.77, 39.78) m, players (53.08, 35.74) m. The fixture
`test_project_scales_normalised_pixels_by_pitch` pins the scale exactly.

**Missing-ball quality** (play blocks 11185–90651 and 110808–190197, 158,857 frames):

| Measure | Value |
|---|---|
| Ball observed | 59.34% |
| Ball imputed (short-gap fill) | 0.03% (51 frames) |
| Ball missing (unresolved) | 40.66% — matches DATA.md's ~41% |
| Gaps in play | 150; median 268 frames, p95 1,269, max 5,537 |
| Gaps ≤ 12 frames (fillable) | 16 (all filled) |
| Gaps > 12 frames | 134 (left missing, by design) |
| `dist_nearest_*` NaN | 52.8% of frames (missing ball plus frames where a team has no observed slot) |
| Median nearest distance | H 3.54 m, A 4.66 m |

The gap profile explains the tiny imputation rate: almost all missingness is in long outages
(median ~11 s), which the conservative rule deliberately does not fill. Only 51 frames in the
whole match are interpolated.

## Issues carried into the Nov 9–11 quality pass

1. `ball_speed` max **720.65 m/s** (p99 is 24.91 m/s) — a physical impossibility, almost
   certainly a jump between observations or an imputation edge. Needs outlier inspection.
2. `rel_vel_nearest_*` can spike when the nearest slot changes identity (documented limit in
   the roadmap) — quantify before trusting it.
3. `voronoi_control_H` is still the distance-based proxy (`src/p1_spatial_features.py:101`);
   assess whether a geometric Voronoi adds value.
4. 12% of frames have a team with no observed slot while the ball is visible — decide whether
   `dist_nearest_*` NaN there is the right contract behaviour (it is, for P3's neutral-evidence
   rule, but confirm).

## Reproduce

```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py            # loader + fixture checks
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a   # regenerate A
.venv/Scripts/python.exe -m unittest discover -s tests -v       # 25 tests, incl. 10 spatial
```
