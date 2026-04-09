from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import csv
import json
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoresearch.agent_report import load_report_entries
from autoresearch.artifacts import load_public_artifacts
from autoresearch.history_report import load_history_rows
from autoresearch.runtime_paths import finalized_artifact_path, history_path, report_path


AGENT_LABELS = {
    "01_ratchet": "01 Ratchet",
    "02_screening_doe": "02 Screening DoE",
    "03_advanced_doe": "03 Advanced DoE",
}

COLORS = {
    "01 Ratchet": "#1768AC",
    "02 Screening DoE": "#D7263D",
    "03 Advanced DoE": "#1B998B",
}


@dataclass(frozen=True)
class RoundPoint:
    round_index: int
    run_id: str
    best_candidate: str
    best_validation: float
    report_text: str


def _format_float(value: float) -> str:
    text = f"{value:.6f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return _format_float(value)


def _load_rounds(history_path: Path, report_path: Path) -> list[RoundPoint]:
    rows = load_history_rows(history_path)
    report_entries = load_report_entries(report_path)
    grouped: dict[str, list] = {}
    run_order: list[str] = []
    for row in rows:
        if row.run_id not in grouped:
            grouped[row.run_id] = []
            run_order.append(row.run_id)
        grouped[row.run_id].append(row)

    rounds: list[RoundPoint] = []
    for round_index, run_id in enumerate(run_order, start=1):
        run_rows = grouped[run_id]
        best_row = min(run_rows, key=lambda item: (item.rank, -item.validation_score, item.candidate))
        rounds.append(
            RoundPoint(
                round_index=round_index,
                run_id=run_id,
                best_candidate=best_row.candidate,
                best_validation=max(item.validation_score for item in run_rows),
                report_text=report_entries[run_id].text if run_id in report_entries else "",
            )
        )
    return rounds


def _candidate_config_text(best_result: dict[str, object]) -> str:
    preprocessing = best_result.get("preprocessing", {})
    model = best_result.get("model", {})
    hidden = model.get("hidden_dims", [])
    return (
        f"norm={preprocessing.get('normalization', 'none')}, "
        f"outlier={preprocessing.get('outlier_strategy', 'none')}, "
        f"proj={preprocessing.get('projection', 'none')}, "
        f"hidden={hidden}, "
        f"activation={model.get('activation', 'relu')}, "
        f"solver={model.get('solver', 'adam')}, "
        f"norm_layer={model.get('normalization_layer', 'none')}, "
        f"wd={_format_float(float(model.get('weight_decay', model.get('alpha', 0.0))))}, "
        f"lr={_format_float(float(model.get('learning_rate_init', 0.001)))}, "
        f"bs={model.get('batch_size', 'auto')}"
    )


def _build_svg(series: list[dict[str, object]], out_path: Path, title: str, round_ticks: tuple[int, ...]) -> None:
    width = 1200
    height = 720
    margin_left = 90
    margin_right = 280
    margin_top = 50
    margin_bottom = 80
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    scores = [
        point
        for row in series
        for values in (row["best_so_far"], row["run_validation"])
        for point in values
    ]
    min_score = min(scores)
    max_score = max(scores)
    padding = max((max_score - min_score) * 0.12, 0.01)
    min_score -= padding
    max_score += padding
    max_rounds = max(len(row["best_so_far"]) for row in series)

    def scale_x(round_index: int) -> float:
        if max_rounds == 1:
            return margin_left + plot_width / 2
        return margin_left + ((round_index - 1) / (max_rounds - 1)) * plot_width

    def scale_y(score: float) -> float:
        return margin_top + (max_score - score) / (max_score - min_score) * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffaf2"/>',
        f'<text x="90" y="30" font-size="28" font-family="Helvetica, Arial, sans-serif" fill="#222">{title}</text>',
    ]

    tick_count = 6
    for tick in range(tick_count):
        ratio = tick / (tick_count - 1)
        score = max_score - ratio * (max_score - min_score)
        y = margin_top + ratio * plot_height
        parts.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}" stroke="#e4dccf" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{margin_left - 12}" y="{y + 5:.1f}" text-anchor="end" font-size="16" font-family="Helvetica, Arial, sans-serif" fill="#444">{score:.3f}</text>'
        )

    for label_round in round_ticks:
        if label_round > max_rounds:
            continue
        x = scale_x(label_round)
        parts.append(
            f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{margin_top + plot_height}" stroke="#efe7da" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{margin_top + plot_height + 28}" text-anchor="middle" font-size="16" font-family="Helvetica, Arial, sans-serif" fill="#444">{label_round}</text>'
        )

    parts.append(
        f'<text x="{margin_left + plot_width / 2:.1f}" y="{height - 22}" text-anchor="middle" font-size="18" font-family="Helvetica, Arial, sans-serif" fill="#333">Round</text>'
    )
    parts.append(
        f'<text x="24" y="{margin_top + plot_height / 2:.1f}" transform="rotate(-90 24 {margin_top + plot_height / 2:.1f})" text-anchor="middle" font-size="18" font-family="Helvetica, Arial, sans-serif" fill="#333">Validation Accuracy</text>'
    )

    legend_x = margin_left + plot_width + 24
    legend_y = margin_top + 32

    for index, row in enumerate(series):
        label = row["agent"]
        color = COLORS[label]
        for round_index, score in enumerate(row["run_validation"], start=1):
            x = scale_x(round_index)
            y = scale_y(score)
            parts.append(
                f'<circle class="raw-point" cx="{x:.2f}" cy="{y:.2f}" r="5.2" fill="{color}" fill-opacity="0.28" stroke="{color}" stroke-opacity="0.55" stroke-width="1.4"/>'
            )
        points = [
            f"{scale_x(round_index):.2f},{scale_y(score):.2f}"
            for round_index, score in enumerate(row["best_so_far"], start=1)
        ]
        parts.append(
            f'<polyline class="best-line" fill="none" stroke="{color}" stroke-width="4" points="{" ".join(points)}"/>'
        )
        y = legend_y + index * 54
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 22}" y2="{y}" stroke="{color}" stroke-width="4"/>')
        parts.append(
            f'<circle cx="{legend_x + 11}" cy="{y}" r="5.2" fill="{color}" fill-opacity="0.28" stroke="{color}" stroke-opacity="0.55" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{legend_x + 32}" y="{y + 5}" font-size="17" font-family="Helvetica, Arial, sans-serif" fill="#222">{label}</text>'
        )
        hidden = row["hidden_test"]
        if hidden is None:
            subtitle = f'best val {row["best_validation"]:.3f} / validation only'
        else:
            subtitle = f'best val {row["best_validation"]:.3f} / hidden {hidden:.3f}'
        parts.append(
            f'<text x="{legend_x + 32}" y="{y + 26}" font-size="14" font-family="Helvetica, Arial, sans-serif" fill="#555">{subtitle}</text>'
        )

    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def build_assets(
    batch_root: Path,
    output_dir: Path,
    output_prefix: str,
    chart_title: str,
    round_ticks: tuple[int, ...],
    root_glob: str,
) -> None:
    summary_rows: list[dict[str, object]] = []
    tictacto_counts: Counter[str] = Counter()

    for root in sorted(batch_root.glob(root_glob)):
        agent_dir = next((root / "agents").iterdir())
        agent_label = AGENT_LABELS.get(agent_dir.name, agent_dir.name)
        rounds = _load_rounds(
            history_path(root, agent_dir),
            report_path(root, agent_dir),
        )
        best_so_far: list[float] = []
        incumbent = float("-inf")
        incumbent_changes = 0
        first_score = rounds[0].best_validation
        best_validation = float("-inf")
        run_of_best = 1

        for round_ in rounds:
            if round_.best_validation > incumbent:
                incumbent = round_.best_validation
                incumbent_changes += 1
            if round_.best_validation > best_validation:
                best_validation = round_.best_validation
                run_of_best = round_.round_index
            best_so_far.append(incumbent)

        final_path = finalized_artifact_path(root, agent_dir.name)
        hidden_test: float | None = None
        if final_path.exists():
            final_artifact = json.loads(final_path.read_text(encoding="utf-8"))
            final_best = final_artifact["best_result"]
            hidden_test = float(final_best["test_score"])
        else:
            best_artifact = max(
                (
                    artifact
                    for artifact in load_public_artifacts(root)
                    if artifact["agent_name"] == agent_dir.name
                ),
                key=lambda artifact: (
                    float(artifact["best_result"]["validation_score"]),
                    str(artifact["run_id"]),
                ),
            )
            final_best = best_artifact["best_result"]

        if agent_dir.name == "03_advanced_doe":
            for round_ in rounds:
                match = re.search(r"move_class=(Tic|Tac|To)", round_.report_text)
                if match:
                    tictacto_counts[match.group(1)] += 1

        summary_rows.append(
            {
                "agent": agent_label,
                "runs": len(rounds),
                "best_validation": best_validation,
                "hidden_test": hidden_test,
                "generalization_gap": None if hidden_test is None else best_validation - hidden_test,
                "run_of_best": run_of_best,
                "gain_vs_run1": best_validation - first_score,
                "mean_best_so_far": sum(best_so_far) / len(best_so_far),
                "incumbent_changes": incumbent_changes,
                "plateau_tail": len(rounds) - run_of_best,
                "best_candidate": str(final_best["candidate_name"]),
                "best_config": _candidate_config_text(final_best),
                "best_so_far": best_so_far,
                "run_validation": [round_.best_validation for round_ in rounds],
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"{output_prefix}_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "agent",
                "runs",
                "best_validation",
                "hidden_test",
                "generalization_gap",
                "run_of_best",
                "gain_vs_run1",
                "mean_best_so_far",
                "incumbent_changes",
                "plateau_tail",
                "best_candidate",
                "best_config",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow({key: value for key, value in row.items() if key not in {"best_so_far", "run_validation"}})

    json_path = output_dir / f"{output_prefix}_summary.json"
    json_path.write_text(
        json.dumps(
            {
                "summary_rows": [
                    {key: value for key, value in row.items() if key not in {"best_so_far", "run_validation"}}
                    for row in summary_rows
                ],
                "series": [
                    {
                        "agent": row["agent"],
                        "best_so_far": row["best_so_far"],
                        "run_validation": row["run_validation"],
                    }
                    for row in summary_rows
                ],
                "tictacto_counts": dict(tictacto_counts),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    svg_path = output_dir / f"{output_prefix}_best_so_far.svg"
    _build_svg(summary_rows, svg_path, chart_title, round_ticks)
    print(csv_path)
    print(json_path)
    print(svg_path)


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--batch-root", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--chart-title", required=True)
    parser.add_argument("--round-ticks", default="1,10,20,30,40,50")
    parser.add_argument("--output-dir", default="presentation/doe_harness/assets")
    parser.add_argument("--root-glob", default="*_root")
    args = parser.parse_args()

    build_assets(
        batch_root=(ROOT / args.batch_root).resolve() if not Path(args.batch_root).is_absolute() else Path(args.batch_root),
        output_dir=(ROOT / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir),
        output_prefix=args.output_prefix,
        chart_title=args.chart_title,
        round_ticks=tuple(int(value) for value in args.round_ticks.split(",") if value.strip()),
        root_glob=args.root_glob,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
