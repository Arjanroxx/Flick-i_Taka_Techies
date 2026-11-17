# P1 — Nov 17 sign-off

Owner: P1. Roadmap: confirm frozen spatial code and input instructions are in the repository.

## Sign-off
- **Frozen spatial code:** `src/p1_spatial_features.py` (unchanged from A candidate 1/frozen A, commit lineage on `p1/nov13-17-freeze-signoff`).
- **Config:** `configs/config.yaml` documents paths, tactical source, pitch, and thresholds (incl. `short_gap: 12`).
- **Input instructions:** `DATA.md`, `README.md`, and `docs/p1/nov14_frozen_a.md` / `docs/p1/nov16_clean_checkout.md` describe bundle placement and `MTAH_DATA_DIR` / `--data-dir` usage (no personal machine paths).
- **Frozen artifact reference:** `artifacts/spatial_features.parquet` SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` (private handoff, not committed).
- **P1 deliverables documented:** `docs/p1/nov06_loader_checks.md`, `nov08_a_v0.md`, `nov09_a_v1.md`, `nov10_11_feature_quality.md`, `nov12_a_candidate1.md`, `nov13_integration.md`, `nov14_frozen_a.md`, `nov15_repro.md`, `nov16_clean_checkout.md`, `nov17_signoff.md`.

**P1 sign-off:** Frozen A (tactical) retained/shipped as documented above. Local full-test/regen blocked this session by pyarrow DLL application-control policy in `.venv`; code/config/docs for reproduction and handoff are in-repo.

Recorded: 2026-11-17
