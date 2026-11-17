# P1 — Clean-checkout verification (Nov 16, recorded 2026-11-17)

Owner: P1. Roadmap: verify input discovery and A generation in a clean-checkout run; confirm documented data paths work without personal machine paths.

## Documented data paths
- Default: `./data` (or `MTAH_DATA_DIR`).
- CLI override: `scripts/run_full_pipeline.py --data-dir <path>`.
- Tactical inputs expected under data dir (e.g. `data/tactical/BAR-ATH_tactical_atd.*`, smart tagging) per `DATA.md`/repo loaders.
- No absolute personal paths are hardcoded in `src/p1_spatial_features.py` or `configs/config.yaml` (`data.directory: null`).

## Verification status
A full clean checkout + regeneration was not executable in this session due to environment constraints (pyarrow DLL blocked in `.venv`; system Python missing deps). Repository state for freeze/sign-off is committed on `p1/nov13-17-freeze-signoff`.

## Clean-checkout procedure (to run on a capable machine)
```powershell
git clone https://github.com/Arjanroxx/Flick-i_Taka_Techies.git
cd Flick-i_Taka_Techies
git checkout p1/nov13-17-freeze-signoff
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
$env:MTAH_DATA_DIR = "C:\path\to\match-data"   # or place bundle under .\data
.venv/Scripts/python.exe scripts/check_p1_loader.py --write-a
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
Expected: `validate("spatial")` passes and `artifacts/spatial_features.parquet` hash matches frozen A (`0E0D790E...`) for identical inputs/config/code.
