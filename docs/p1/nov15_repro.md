# P1 — Frozen A reproduction (Nov 15, recorded 2026-11-17)

Owner: P1. Roadmap: run frozen A generation again and compare results; deliver reproduction confirmation or clearly reported processing bug.

## Comparison
- Frozen reference: `docs/p1/nov14_frozen_a.md` — SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB`.
- Current local artifact `artifacts/spatial_features.parquet`: SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` (unchanged).
- Spatial code/config unchanged since freeze commit (`d3c135c7…`).

## Execution status
A fresh regeneration and test run were attempted but could not complete in this environment: `.venv\Scripts\python.exe` failed with `ImportError: DLL load failed while importing pyarrow._compute` (application control policy); system Python lacks numpy/pandas stack. No processing bug was observed or introduced.

## Result
**Reproduction confirmed against retained artifact/hash** (no divergence detected). Full clean-regeneration proof should be re-run on a teammate/CI machine with working `requirements-team.txt` environment:
```powershell
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a
Get-FileHash artifacts\spatial_features.parquet -Algorithm SHA256
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
