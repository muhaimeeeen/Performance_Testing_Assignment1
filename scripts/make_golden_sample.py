"""Draw the golden-set candidate sample from Group 9's rows (9000-9999).

Stratified by the (noisy) source label so every category is represented,
then shuffled so labellers do not see tickets grouped by category.
The source label is NOT written to the labelling files.

Usage: python scripts/make_golden_sample.py
"""
import csv
import random
from collections import defaultdict
from pathlib import Path

SEED = 9
SAMPLE_SIZE = 160          # 150 minimum + buffer for "fits none" exclusions
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "team09_rows.csv"
OUT = ROOT / "golden" / "sample_160.csv"


def main() -> None:
    with SRC.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1000, f"expected 1000 team rows, got {len(rows)}"
    assert all(9000 <= int(r["row"]) <= 9999 for r in rows)

    by_label = defaultdict(list)
    for r in rows:
        by_label[r["source_label"]].append(r)

    rng = random.Random(SEED)
    labels = sorted(by_label)
    base, extra = divmod(SAMPLE_SIZE, len(labels))
    picked = []
    for i, label in enumerate(labels):
        k = base + (1 if i < extra else 0)
        picked.extend(rng.sample(by_label[label], k))
    rng.shuffle(picked)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "row", "narrative"])
        for i, r in enumerate(picked, 1):
            w.writerow([i, r["row"], r["narrative"]])
    print(f"wrote {len(picked)} tickets to {OUT.relative_to(ROOT)} (seed={SEED})")


if __name__ == "__main__":
    main()
