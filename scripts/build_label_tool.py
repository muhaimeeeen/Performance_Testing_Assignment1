"""Build the offline labelling page (golden/label_tool.html) from golden/sample_160.csv.

The page is self-contained: open it in Chrome/Safari, no server or network needed.
Usage: python scripts/build_label_tool.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "golden" / "sample_160.csv"
TEMPLATE = ROOT / "scripts" / "label_tool_template.html"
OUT = ROOT / "golden" / "label_tool.html"


def main() -> None:
    with SAMPLE.open(encoding="utf-8", newline="") as f:
        items = [{"item": int(r["item"]), "row": int(r["row"]), "text": r["narrative"]}
                 for r in csv.DictReader(f)]
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__TICKETS_JSON__", payload)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(items)} tickets")


if __name__ == "__main__":
    main()
