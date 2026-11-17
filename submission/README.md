# Flick-i Taka Techies — final submission

Upload **Flick-i Taka Techies.csv** and **Flick-i Taka Techies.pdf** from this folder. Use team name **Flick-i Taka Techies** and public repository URL `https://github.com/Arjanroxx/Flick-i_Taka_Techies`.

This is the frozen Step 6 duration model. No experimental ownership classifiers, split verifiers, boundary refinements, hosted models or arbitration overrides are enabled. `configs/final_submission.yaml` is authoritative; `configs/config.yaml` remains the older development baseline.

## Reproduce exactly

From the repository root, use Python 3.12 and the licensed original tactical bundle:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
.venv/Scripts/python.exe scripts/build_submission.py --data-dir 'C:/path/to/dataset'
```

Alternatively set `MTAH_DATA_DIR` and omit `--data-dir`. Reproduction needs no external training-data download: the fitted duration scale is frozen in the configuration. The command regenerates the complete CSV from original tracking/tagging, applies canonical UTF-8/LF formatting, validates all 199,319 rows and requires the exact checksum in `manifest.json`. Source hashes normalize CRLF/LF differences only. Runtime does not use the public ground truth.

The PDF describes the final method, external training data, possession rules, validation, limitations and reproduction. Its generation script is `scripts/generate_submission_pdf.py`; document-only dependencies are separate from the inference runtime.

Public sanity spellF1: **0.557143**; H/A/D macroF1: **0.688999**. These are five-minute scores, not full-match or qualification guarantees. The study reports retain uncertainty and methodology details. No licensed tracking/video is included here.
