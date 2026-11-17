# P1 → P3 Handoff: Frozen A (spatial features)

**Date:** 2026-11-17  
**Branch:** `p1/nov13-17-freeze-signoff`  
**Head commit:** `9ccd1d9d4b038748894e19912d9b2f100bc6e869` (`P1 Nov 13-17: integration check, freeze A, repro, sign-off docs`)  
**Spatial implementation commit (frozen):** `d3c135c793f96ffcb7c824c4f371d76aa5cf81f6` — `src/p1_spatial_features.py` unchanged since A candidate 1.

## Readiness check
| Check | Status | Evidence |
|---|---|---|
| Artifact present | **OK** | `artifacts/spatial_features.parquet` (6,042,882 bytes, last written 2026-11-12 14:54:36 local) |
| Hash matches frozen A | **OK** | SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` (see `docs/p1/nov12_a_candidate1.md`, `nov14_frozen_a.md`) |
| Contract/schema/rows/halves | **OK (per recorded validation)** | `validate("spatial", table)` passed at freeze; 199,319 rows; official play blocks 11185–90651 & 110808–190197, `half=0` outside (documented in `docs/p1/nov12_a_candidate1.md`) |
| Unit tests / fresh regen in this session | **Not re-run (env constraint)** | `.venv` hit `ImportError: DLL load failed while importing pyarrow._compute` (application control); system Python lacks deps. No code/config changes made; artifact unchanged from validated freeze. |
| Inputs available | **OK (local)** | `data/tactical/` present (`BAR-ATH_tactical_atd.txt/xml`, `BAR-ATH_tactical_smart_tagging.xml`, `BAR-ATH_tactical_homography.csv`, `BAR-ATH_tactical.mp4`) + `configs/config.yaml` (`data.source: tactical`, `short_gap: 12`, pitch 105.3x68) |

**Verdict:** Handoff is **ready for P3 consumption** based on frozen, hash-verified artifact and documented validation. Re-run tests/regen on a working `requirements-team.txt` environment for independent confirmation if required.

## Handoff package (A)
- **File:** `artifacts/spatial_features.parquet` (**private/local, not in Git**)
- **Private location:** share out-of-band per team process (e.g. agreed private drive/channel). Local reference path in this workspace: `D:\Flick-i_Taka_Techies\artifacts\spatial_features.parquet`.
- **Code commit that created/froze A:** `d3c135c793f96ffcb7c824c4f371d76aa5cf81f6` (`src/p1_spatial_features.py`), config at same lineage (`configs/config.yaml`).
- **Input version:** Tactical bundle delivered Nov 6 (BAR-ATH), unpacked under `data/tactical/`; no personal machine paths in code/config (`data.directory: null`, use `MTAH_DATA_DIR` or `--data-dir`).
- **Contract check:** `validate("spatial", table)` — **passed** at A candidate 1/freeze (see `docs/p1/nov12_a_candidate1.md`).

## Regeneration (repro)
```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
# place bundle under .\data or set $env:MTAH_DATA_DIR / use --data-dir
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a
.venv/Scripts/python.exe -m unittest discover -s tests -v
Get-FileHash artifacts\spatial_features.parquet -Algorithm SHA256
```
Expected: hash `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` for identical inputs/config/code.

## Known limitations (carry-forward for P3)
- Ball missing ~40.7% of play frames; only short in-half gaps (≤12, endpoint speed ≤40 m/s) filled (19 frames). Handle NaN distances/evidence.
- Imputed/fill-adjacent derivatives are NaN (no interpolation residue); tracker teleports persist in observed data.
- 184 in-play frames with no observed H slot (end of half 1) → NaN distances; treat as neutral/missing evidence per contract.
- `voronoi_control_H` is a distance proxy; broadcast unused.
- Full details: `docs/p1/nov12_a_candidate1.md`, `nov09_a_v1.md`, `nov10_11_feature_quality.md`.

## For P3
Use this Frozen A with the corresponding frozen/validated B (`artifacts/deadball_mask.parquet`) to produce C. Record A hash/commit in your handoff log. Downstream export uses X outside play; contract spatial uses `half=0` outside play.
