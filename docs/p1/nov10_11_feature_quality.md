# P1 — Nov 10/11: imputation comparison and feature-quality summary (completed Nov 12)

Owner: P1. Nov 10 deliverable: compare the imputation rule against a candidate alternative and
only keep an update if evidence supports it. Nov 11: duplicate slots, nearest distances,
relative-velocity spikes, and whether geometric Voronoi control adds value; publish A v2 with a
feature-quality summary.

## Nov 10 — short linear fill vs speed-ceiling fill

Candidate alternative: refuse to interpolate across endpoints whose implied average speed
exceeds 40 m/s (above observed p99 ≈ 24.6 m/s; real football tops out near 36 m/s).

Two-way comparison on the delivered match (no external labels exist for this match, so the
fixtures and the enforceability of the evidence are the support):

| Fill candidate | Frames | Endpoints (implied speed) | Verdict |
|---|---|---|---|
| v0: fill all short gaps ≤ 12 | 51 (15 runs) | gaps of ≤12 frames; spans 3.3–86.5 m | 11 runs imply >40 m/s on replay (up to ~180 m/s — impossible) |
| v1: speed-ceiling fill (adopted) | 19 (4 runs) | 31.7, 37.9, 25.9, 36.5 m/s implied | all four remain physically plausible — a 12-frame 16.5 m clearance at 31.7 m/s is a plausible struck clearance |

Rejected work had no evidential value to anyone: P3 already demotes imputed frames to neutral
evidence (`known=False` in `p3_sequence_model.run`), so the 32 removed frames simply stop
poisoning positions, distances and velocities. The rule is one global constant, not a
frame-specific hand-coded correction, so no rule tuning was performed against any outcomes.

Metrica sample data cannot arbitrate this (no frame-level labels, per the P4 Nov 6 assessment);
the fixture `test_teleport_gap_not_interpolated` pins the rejected case.

## Nov 11 — feature quality

**Duplicate slots / integrity.** 46 slots (24 H, 22 A); no empty team; slot counts stable.
Duplicate *identities* across teams cannot occur with metadata slot teams. Identity switches
within a team are visible as position teleports between frames — see relative velocity below.
`np.isfinite` screening keeps unresolved observations from ever producing a finite distance.

**Nearest distances.** While the ball is observed: median nearest distance H 3.54 m / A 4.66 m.
184 in-play frames have zero observed H slots (never for A), produced by occlusion and reported
by the contract as NaN — the correct behaviour, matched by P3's neutral handling.

**Relative-velocity spikes.** `rel_vel` p99 ≈ 24 m/s, p99.9 ≈ 56 m/s, max 108.9 (was 723 pre-v1).
Spikes remaining are observed→observed jumps where the nearest track slot changes across the
step (documented ATD identity fragmentation). They are honest local kinematics; they should not
be thresholded away without external labels to validate against.

**Voronoi control — keep the distance proxy.** `voronoi_control_H` correlates 0.81 with
`dA − dH` and 0.84 with the dH<dA indicator: it is close to a monotone transform of the same
evidence P3 already consumes. A geometric cell-area control (46 sites, role-free) would add
frames of compute and a maintenance surface for no new information P3 can currently use — P3's
emission reads only `dist_nearest_H/A`, `ball_is_imputed` and `gap_length_frames`.
Assessment: no value for the current stack; revisit only if P3's emissions are extended and
validated externally.

**Expected/values for v1 vs v0 inputs for P2** (B consumes positions, speeds, acceleration and
the imputation flag): P2's rule of rejecting derivatives that touch unobserved frames now
applies cleanly — every frame with an unobservable derivative carries NaN, not a fill residue.

**A v2 decision.** No evidence supports changing the geometry contract beyond v1. A v2 is
therefore *retained from v1* — the agreed position for the Nov 12 candidate freeze is the
current code.

## Command

```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a  # rebuild A from current code
```
