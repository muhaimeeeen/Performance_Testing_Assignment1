"""Inter-annotator agreement and golden-set finalisation.

  python scripts/agreement.py kappa    golden/labels/labels_a.csv golden/labels/labels_b.csv
      -> prints Cohen's kappa, writes golden/agreement_report.md and
         golden/resolution_log.csv (one row per disagreement, to be filled in).

  python scripts/agreement.py finalise golden/labels/labels_a.csv golden/labels/labels_b.csv
      -> requires every resolution_log row to have final_label filled in;
         writes golden/golden_set.csv (agreed + resolved labels, None excluded).
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "golden"
CATS = ["Credit reporting", "Debt collection", "Mortgage", "Credit card",
        "Bank account or service", "Consumer loan", "Money transfer or service"]
VALID = set(CATS) | {"None"}


def read_labels(path: Path) -> tuple[str, dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path}: empty file")
    who = rows[0]["labeller"]
    out = {}
    for r in rows:
        if r["label"] not in VALID:
            sys.exit(f"{path}: item {r['item']} has missing/invalid label {r['label']!r}")
        out[int(r["item"])] = r
    return who, out


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float, float, float]:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return kappa, po, pe


def kappa_cmd(fa: Path, fb: Path) -> None:
    wa, la = read_labels(fa)
    wb, lb = read_labels(fb)
    if wa == wb:
        sys.exit("both files have the same labeller name; labels must come from two people")
    if set(la) != set(lb):
        sys.exit("label files cover different items")
    items = sorted(la)
    a = [la[i]["label"] for i in items]
    b = [lb[i]["label"] for i in items]
    kappa, po, pe = cohen_kappa(a, b)

    labs = CATS + ["None"]
    matrix = {x: Counter() for x in labs}
    for x, y in zip(a, b):
        matrix[x][y] += 1

    lines = [f"# Inter-annotator agreement\n",
             f"- Labellers: **{wa}** (A) vs **{wb}** (B)",
             f"- Items: {len(items)}",
             f"- Observed agreement p_o: {po:.3f}",
             f"- Chance agreement p_e: {pe:.3f}",
             f"- **Cohen's kappa: {kappa:.3f}**",
             f"- Disagreements: {sum(x != y for x, y in zip(a, b))}\n",
             "## Per-category agreement (A's label as reference)\n",
             "| Category | A count | B count | Both agree | Positive agreement |",
             "|---|---|---|---|---|"]
    ca, cb = Counter(a), Counter(b)
    for c in labs:
        both = matrix[c][c]
        pa = 2 * both / (ca[c] + cb[c]) if (ca[c] + cb[c]) else float("nan")
        lines.append(f"| {c} | {ca[c]} | {cb[c]} | {both} | {pa:.2f} |")
    lines += ["\n## Cross-tab (rows = A, columns = B)\n",
              "| A \\ B | " + " | ".join(labs) + " |", "|---" * (len(labs) + 1) + "|"]
    for x in labs:
        lines.append(f"| {x} | " + " | ".join(str(matrix[x][y]) for y in labs) + " |")
    (GOLDEN / "agreement_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    log = GOLDEN / "resolution_log.csv"
    if log.exists():
        print(f"{log.name} already exists; not overwriting (delete it to regenerate)")
    else:
        with log.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item", "row", f"label_{wa}", f"note_{wa}", f"label_{wb}", f"note_{wb}",
                        "final_label", "rule_applied", "rationale", "protocol_change"])
            for i in items:
                if la[i]["label"] != lb[i]["label"]:
                    w.writerow([i, la[i]["row"], la[i]["label"], la[i]["note"],
                                lb[i]["label"], lb[i]["note"], "", "", "", ""])
    print(f"kappa={kappa:.3f} po={po:.3f} pe={pe:.3f} -> agreement_report.md, resolution_log.csv")


def finalise_cmd(fa: Path, fb: Path) -> None:
    _, la = read_labels(fa)
    _, lb = read_labels(fb)
    with (GOLDEN / "resolution_log.csv").open(encoding="utf-8", newline="") as f:
        res = {int(r["item"]): r for r in csv.DictReader(f)}
    missing = [i for i, r in res.items() if r["final_label"] not in VALID]
    if missing:
        sys.exit(f"resolution_log.csv: final_label missing/invalid for items {missing}")

    out, excluded = [], []
    for i in sorted(la):
        final = res[i]["final_label"] if i in res else la[i]["label"]
        if i not in res and la[i]["label"] != lb[i]["label"]:
            sys.exit(f"item {i} disagrees but has no resolution")
        (excluded if final == "None" else out).append((i, la[i]["row"], final, "resolved" if i in res else "agreed"))
    with (GOLDEN / "golden_set.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "row", "golden_label", "how"])
        w.writerows(out)
    print(f"golden_set.csv: {len(out)} tickets ({len(excluded)} excluded as None)")
    print(Counter(r[2] for r in out))
    if len(out) < 150:
        print("WARNING: fewer than 150 tickets — brief requires 150 to 200")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in {"kappa", "finalise"}:
        sys.exit(__doc__)
    {"kappa": kappa_cmd, "finalise": finalise_cmd}[sys.argv[1]](Path(sys.argv[2]), Path(sys.argv[3]))
