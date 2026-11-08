"""Fetch and validate an attributed public other-match event sample."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.p4_arbiter_and_eval import METRICA_SAMPLE_REVISION, METRICA_SAMPLE_URL, load_metrica_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Fetch the pinned public event file")
    parser.add_argument("--path", type=Path, default=ROOT / "artifacts/external/metrica/Sample_Game_1_RawEventsData.csv")
    args = parser.parse_args()
    if args.download:
        args.path.parent.mkdir(parents=True, exist_ok=True)
        # Validate the temporary download before replacing an existing local sample.
        temporary = args.path.with_suffix(".download.csv")
        try:
            with urlopen(METRICA_SAMPLE_URL, timeout=60) as response:
                temporary.write_bytes(response.read())
            load_metrica_events(temporary)
            temporary.replace(args.path)
        finally:
            temporary.unlink(missing_ok=True)
    events = load_metrica_events(args.path)
    report = {
        "source": "Metrica Sports Sample Data, Sample Game 1",
        "source_revision": METRICA_SAMPLE_REVISION,
        "source_url": METRICA_SAMPLE_URL,
        "sha256": hashlib.sha256(args.path.read_bytes()).hexdigest(),
        "events": len(events),
        "teams": sorted(events.Team.unique().tolist()),
        "periods": sorted(events.Period.unique().tolist()),
        "event_counts": events.Type.value_counts().to_dict(),
        "reversed_intervals": events.attrs["reversed_intervals"],
        "frame_possession_ground_truth_available": False,
        "assessment": "Event-level development only; continuous possession labels need separate validation.",
    }
    output = args.path.with_suffix(".assessment.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Validated {len(events)} public events. Assessment saved to {output}")


if __name__ == "__main__":
    main()
