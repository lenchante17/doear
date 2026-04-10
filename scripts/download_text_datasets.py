from __future__ import annotations

from pathlib import Path
import csv


ROOT = Path(__file__).resolve().parent.parent
NEWS_TARGET = ROOT / "data" / "twenty_newsgroups" / "twenty_newsgroups.csv"


def _fetch_twenty_newsgroups(categories: list[str] | None = None):
    from sklearn.datasets import fetch_20newsgroups

    return fetch_20newsgroups(
        subset="all",
        categories=categories,
        data_home=str(ROOT / "data" / "sklearn_cache"),
        remove=("headers", "footers", "quotes"),
    )


def _write_text_rows(target: Path, texts: list[str], labels: list[int]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["label", "text"])
        writer.writeheader()
        for text, label in zip(texts, labels, strict=True):
            writer.writerow({"label": label, "text": text.replace("\x00", " ")})
    print(f"write {target} {len(texts)} rows")


def build_twenty_newsgroups() -> None:
    dataset = _fetch_twenty_newsgroups()
    _write_text_rows(NEWS_TARGET, list(dataset.data), [int(label) for label in dataset.target])


def main() -> int:
    build_twenty_newsgroups()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
