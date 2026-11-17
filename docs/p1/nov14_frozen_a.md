# P1 — Frozen A (Nov 14, recorded 2026-11-17)

Owner: P1. Roadmap: choose spatial version to ship; deliver frozen A, code commit, and regeneration command.

## Frozen A
| Field | Value |
|---|---|
| Artifact | `artifacts/spatial_features.parquet` (local/private, not committed) |
| SHA-256 | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` (A candidate 1 retained; see `docs/p1/nov13_integration.md`) |
| Spatial code | `src/p1_spatial_features.py` @ commit `d3c135c793f96ffcb7c824c4f371d76aa5cf81f6` (branch `p1/nov13-17-freeze-signoff`) |
| Config | `configs/config.yaml` — `data.source: tactical`, `thresholds.short_gap: 12`, `pitch: {length: 105.3, width: 68}` |
| Contract | `validate("spatial", table)` required; 199,319 rows, official half blocks, imputed only for short in-half gaps with endpoint speed ceiling per implementation |

## Regeneration command
From repo root with licensed tactical bundle unpacked under `data/` (or `MTAH_DATA_DIR` / `--data-dir` pointing to it):
```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a
# or full pipeline A stage: .venv/Scripts/python.exe scripts/run_full_pipeline.py
```

## Scope / notes
- **Tactical feed only.** Broadcast not shipped: not aligned/verified to tactical timeline and not required for spatial contract.
- Inputs are discovered via project data-dir conventions (`data/tactical/*`); no personal machine paths committed.
- Share `artifacts/spatial_features.parquet` and config privately per team process.
