# P1 — Nov 13 integration check (2026-11-17)

Owner: P1. Roadmap: resolve reproducible feature-processing bugs and review long-gap behavior; deliver final proposed A changes or confirmation that A candidate 1 is retained.

## Checks performed
- Branch: `p1/nov13-17-freeze-signoff` @ `d3c135c793f96ffcb7c824c4f371d76aa5cf81f6` (spatial code unchanged from A candidate 1).
- Inputs present: `data/tactical/` (ATD txt/xml, smart tagging xml, homography csv, tactical mp4).
- Existing artifact: `artifacts/spatial_features.parquet` SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` (matches A candidate 1 in `docs/p1/nov12_a_candidate1.md`).
- Config: `configs/config.yaml` (`short_gap: 12`, tactical source, pitch 105.3x68).
- Unit tests / regeneration: not executed in this session because the local `.venv` Python hit `ImportError: DLL load failed while importing _compute` (pyarrow blocked by application control) and system Python lacks project dependencies. No code changes were made.

## Long-gap / bug review
No new reproducible processing bugs identified from code review against the documented A candidate 1 limitations (40.7% missing ball in play, long outages by design, tracker teleports in observed data, broadcast unused). Prior fixes (NaN derivatives on filled/imputed-adjacent steps, speed-ceiling fill) remain in `src/p1_spatial_features.py` at this commit.

## Decision
**A candidate 1 retained.** No final proposed A changes. Frozen spatial deliverable proceeds from this code/input contract.
