"""Create isolated synthetic handoffs for Day 1 development."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.contracts import day1_mocks, write


def main():
    for kind, filename, table in zip(
        ("spatial", "deadball"), ("spatial_features.parquet", "deadball_mask.parquet"), day1_mocks()
    ):
        path = ROOT / "artifacts/mock" / filename
        write(kind, table, path)
        print(path)


if __name__ == "__main__":
    main()
