from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "presentation" / "doe_harness" / "assets"

DATASETS = (
    (
        "fashion_mnist",
        "Fashion-MNIST",
        Path("/tmp/toy_research_isolated_experiments/20260410T005018Z/fashion_mnist_real"),
    ),
    (
        "twenty_newsgroups",
        "Twenty Newsgroups",
        Path("/tmp/toy_research_isolated_experiments/20260410T015915Z/twenty_newsgroups_real"),
    ),
    (
        "sms_spam",
        "SMS Spam",
        Path("/tmp/toy_research_isolated_experiments/20260410T022533Z/sms_spam_real"),
    ),
    (
        "cifar10",
        "CIFAR-10",
        Path("/tmp/toy_research_isolated_experiments/20260410T023759Z/cifar10_real"),
    ),
)

Q1_GROUPS = OrderedDict(
    (
        (
            "plain_agent",
            {
                "label": "Plain Agent",
                "conditions": ("ratchet_plain", "screening_plain", "advanced_plain"),
                "color": "#2563eb",
            },
        ),
        (
            "agent_tpe",
            {
                "label": "Agent + TPE",
                "conditions": ("ratchet_tpe", "screening_tpe", "advanced_tpe"),
                "color": "#f59e0b",
            },
        ),
        (
            "agent_smac",
            {
                "label": "Agent + SMAC",
                "conditions": ("ratchet_smac", "screening_smac", "advanced_smac"),
                "color": "#16a34a",
            },
        ),
        (
            "agent_tpe_smac",
            {
                "label": "Agent + TPE+SMAC",
                "conditions": ("ratchet_tpe_smac", "screening_tpe_smac", "advanced_tpe_smac"),
                "color": "#dc2626",
            },
        ),
        (
            "direct",
            {
                "label": "Direct",
                "conditions": ("tpe_direct", "smac_direct"),
                "color": "#64748b",
            },
        ),
    )
)

Q2_GROUPS = OrderedDict(
    (
        (
            "ratchet",
            {
                "label": "Ratchet",
                "conditions": ("ratchet_plain", "ratchet_tpe", "ratchet_smac", "ratchet_tpe_smac"),
                "color": "#2563eb",
            },
        ),
        (
            "screening",
            {
                "label": "Screening",
                "conditions": ("screening_plain", "screening_tpe", "screening_smac", "screening_tpe_smac"),
                "color": "#f59e0b",
            },
        ),
        (
            "advanced",
            {
                "label": "Advanced",
                "conditions": ("advanced_plain", "advanced_tpe", "advanced_smac", "advanced_tpe_smac"),
                "color": "#16a34a",
            },
        ),
    )
)

CONDITION_SHORT = {
    "ratchet_plain": "Rat Plain",
    "screening_plain": "Scr Plain",
    "advanced_plain": "Adv Plain",
    "tpe_direct": "TPE Dir",
    "smac_direct": "SMAC Dir",
    "ratchet_tpe": "Rat TPE",
    "screening_tpe": "Scr TPE",
    "advanced_tpe": "Adv TPE",
    "ratchet_smac": "Rat SMAC",
    "screening_smac": "Scr SMAC",
    "advanced_smac": "Adv SMAC",
    "ratchet_tpe_smac": "Rat T+S",
    "screening_tpe_smac": "Scr T+S",
    "advanced_tpe_smac": "Adv T+S",
}

TEXT = "#1f2328"
SUBTLE = "#5b6470"
GRID = "#e8ebf0"
BG = "#fffdf8"
WHITE = "#ffffff"


@dataclass(frozen=True)
class EvalPoint:
    run_id: str
    condition_name: str
    candidate_name: str
    validation_score: float


@dataclass(frozen=True)
class TableCell:
    best_validation: float
    winner_text: str
    winner_count: int
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class GroupSeries:
    label: str
    color: str
    evaluations: tuple[EvalPoint, ...]
    best_so_far: tuple[float, ...]
    scatter_points: tuple[tuple[int, float], ...]
    cell: TableCell


def _load_run_evaluations(condition_root: Path, condition_name: str) -> list[EvalPoint]:
    runs_dir = condition_root / ".work" / "runs"
    rows: list[EvalPoint] = []
    for path in sorted(runs_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload["best_result"]
        rows.append(
            EvalPoint(
                run_id=str(payload["run_id"]),
                condition_name=condition_name,
                candidate_name=str(result["candidate_name"]),
                validation_score=float(result["validation_score"]),
            )
        )
    rows.sort(key=lambda row: row.run_id)
    return rows


def _load_finalized_best(condition_root: Path, condition_name: str) -> tuple[float, float]:
    path = condition_root / ".work" / "finalized" / f"{condition_name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    best = payload["best_result"]
    return float(best["validation_score"]), float(best["test_score"])


def _winner_text(conditions: list[str]) -> str:
    if len(conditions) == 1:
        return CONDITION_SHORT.get(conditions[0], conditions[0])
    return f"tie x{len(conditions)}"


def _build_group_series(dataset_root: Path, group_spec: dict[str, object]) -> GroupSeries:
    condition_names = tuple(group_spec["conditions"])
    evaluations: list[EvalPoint] = []
    best_rows: list[tuple[str, float, float]] = []
    for condition_name in condition_names:
        condition_root = dataset_root / condition_name
        evaluations.extend(_load_run_evaluations(condition_root, condition_name))
        best_rows.append((condition_name, *_load_finalized_best(condition_root, condition_name)))
    evaluations.sort(key=lambda row: row.run_id)

    best_so_far: list[float] = []
    scatter_points: list[tuple[int, float]] = []
    incumbent = float("-inf")
    for index, row in enumerate(evaluations, start=1):
        if row.validation_score > incumbent:
            incumbent = row.validation_score
        else:
            scatter_points.append((index, row.validation_score))
        best_so_far.append(incumbent)

    winner_value = max(row[1] for row in best_rows)
    winners = sorted([row[0] for row in best_rows if row[1] == winner_value])
    return GroupSeries(
        label=str(group_spec["label"]),
        color=str(group_spec["color"]),
        evaluations=tuple(evaluations),
        best_so_far=tuple(best_so_far),
        scatter_points=tuple(scatter_points),
        cell=TableCell(
            best_validation=winner_value,
            winner_text=_winner_text(winners),
            winner_count=len(winners),
            conditions=tuple(winners),
        ),
    )


def _summaries_for_groups(group_specs: OrderedDict[str, dict[str, object]]) -> dict[str, dict[str, GroupSeries]]:
    dataset_groups: dict[str, dict[str, GroupSeries]] = {}
    for dataset_key, _, dataset_root in DATASETS:
        dataset_groups[dataset_key] = {}
        for group_key, group_spec in group_specs.items():
            dataset_groups[dataset_key][group_key] = _build_group_series(dataset_root, group_spec)
    return dataset_groups


def _svg_header(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        f".bg{{fill:{BG};}}",
        f".title{{font-family:Helvetica,Arial,sans-serif;font-size:30px;font-weight:700;fill:{TEXT};}}",
        f".subtitle{{font-family:Helvetica,Arial,sans-serif;font-size:16px;fill:{SUBTLE};}}",
        f".label{{font-family:Helvetica,Arial,sans-serif;fill:{TEXT};}}",
        f".subtle{{font-family:Helvetica,Arial,sans-serif;fill:{SUBTLE};}}",
        f".grid{{stroke:{GRID};stroke-width:1;}}",
        "</style>",
        f'<rect class="bg" width="{width}" height="{height}"/>',
        f'<text class="title" x="54" y="38">{title}</text>',
        f'<text class="subtitle" x="54" y="63">{subtitle}</text>',
    ]


def _build_table_svg(
    out_path: Path,
    title: str,
    subtitle: str,
    groups: OrderedDict[str, dict[str, object]],
    summaries: dict[str, dict[str, GroupSeries]],
) -> None:
    width = 1460
    header_height = 74
    row_height = 92
    label_width = 250
    col_width = 288
    total_rows = len(groups) + 1
    height = 120 + header_height + row_height * total_rows + 30
    parts = _svg_header(width, height, title, subtitle)
    table_x = 54
    table_y = 96

    parts.append(
        f'<rect x="{table_x}" y="{table_y}" width="{label_width + col_width * len(DATASETS)}" height="{header_height + row_height * len(groups)}" rx="20" fill="{WHITE}" stroke="#d7dce3" stroke-width="1.2"/>'
    )

    for index, (_, label, _) in enumerate(DATASETS):
        x = table_x + label_width + col_width * index
        parts.append(
            f'<rect x="{x}" y="{table_y}" width="{col_width}" height="{header_height}" fill="#f8fafc"/>'
        )
        parts.append(
            f'<text class="label" x="{x + col_width / 2:.1f}" y="{table_y + 44:.1f}" text-anchor="middle" font-size="20" font-weight="700">{label}</text>'
        )
    parts.append(
        f'<rect x="{table_x}" y="{table_y}" width="{label_width}" height="{header_height}" fill="#f8fafc"/>'
    )
    parts.append(
        f'<text class="label" x="{table_x + 22}" y="{table_y + 44:.1f}" font-size="20" font-weight="700">Comparison Group</text>'
    )

    for row_index, (group_key, group_spec) in enumerate(groups.items()):
        y = table_y + header_height + row_height * row_index
        fill = "#ffffff" if row_index % 2 == 0 else "#fcfcfd"
        parts.append(
            f'<rect x="{table_x}" y="{y}" width="{label_width + col_width * len(DATASETS)}" height="{row_height}" fill="{fill}"/>'
        )
        parts.append(
            f'<line class="grid" x1="{table_x}" y1="{y}" x2="{table_x + label_width + col_width * len(DATASETS)}" y2="{y}"/>'
        )
        parts.append(
            f'<text x="{table_x + 22}" y="{y + 40:.1f}" font-family="Helvetica,Arial,sans-serif" font-size="21" font-weight="700" fill="{group_spec["color"]}">{group_spec["label"]}</text>'
        )
        parts.append(
            f'<text class="subtle" x="{table_x + 22}" y="{y + 64:.1f}" font-size="13">best val among group conditions</text>'
        )

        for col_index, (dataset_key, _, _) in enumerate(DATASETS):
            x = table_x + label_width + col_width * col_index
            cell = summaries[dataset_key][group_key].cell
            parts.append(
                f'<line class="grid" x1="{x}" y1="{table_y}" x2="{x}" y2="{table_y + header_height + row_height * len(groups)}"/>'
            )
            parts.append(
                f'<text class="label" x="{x + col_width / 2:.1f}" y="{y + 38:.1f}" text-anchor="middle" font-size="24" font-weight="700">{cell.best_validation:.3f}</text>'
            )
            parts.append(
                f'<text class="subtle" x="{x + col_width / 2:.1f}" y="{y + 62:.1f}" text-anchor="middle" font-size="14">{cell.winner_text}</text>'
            )

    bottom_y = table_y + header_height + row_height * len(groups)
    parts.append(f'<line class="grid" x1="{table_x}" y1="{bottom_y}" x2="{table_x + label_width + col_width * len(DATASETS)}" y2="{bottom_y}"/>')
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _score_bounds(series: list[GroupSeries]) -> tuple[float, float]:
    values: list[float] = []
    for row in series:
        values.extend(row.best_so_far)
        values.extend(score for _, score in row.scatter_points)
    low = min(values)
    high = max(values)
    span = max(high - low, 0.01)
    return low - max(span * 0.15, 0.01), high + max(span * 0.08, 0.01)


def _build_history_panel_svg(
    out_path: Path,
    title: str,
    subtitle: str,
    groups: OrderedDict[str, dict[str, object]],
    summaries: dict[str, dict[str, GroupSeries]],
    dataset_keys: tuple[str, str],
) -> None:
    width = 1460
    height = 820
    header_h = 92
    legend_h = 70
    panel_gap = 32
    outer_margin = 54
    panel_width = (width - outer_margin * 2 - panel_gap) / 2
    panel_height = height - header_h - legend_h - 40

    parts = _svg_header(width, height, title, subtitle)

    for legend_index, (_, group_spec) in enumerate(groups.items()):
        lx = 54 + legend_index * 260
        ly = 86
        color = group_spec["color"]
        parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx + 24}" y2="{ly}" stroke="{color}" stroke-width="3.5"/>')
        parts.append(f'<circle cx="{lx + 12}" cy="{ly + 18}" r="4" fill="{color}" opacity="0.28"/>')
        parts.append(f'<text class="label" x="{lx + 34}" y="{ly + 5}" font-size="16">{group_spec["label"]}</text>')
        parts.append(f'<text class="subtle" x="{lx + 34}" y="{ly + 23}" font-size="13">line=best val, scatter=other evals</text>')

    for panel_index, dataset_key in enumerate(dataset_keys):
        dataset_label = next(label for key, label, _ in DATASETS if key == dataset_key)
        panel_x = outer_margin + panel_index * (panel_width + panel_gap)
        panel_y = header_h + 10
        plot_left = panel_x + 62
        plot_top = panel_y + 34
        plot_width = panel_width - 86
        plot_height = panel_height - 72
        series = [summaries[dataset_key][group_key] for group_key in groups.keys()]
        min_score, max_score = _score_bounds(series)
        max_steps = max(len(row.evaluations) for row in series)

        parts.append(
            f'<rect x="{panel_x}" y="{panel_y}" width="{panel_width}" height="{panel_height}" rx="24" fill="{WHITE}" stroke="#d7dce3" stroke-width="1.1"/>'
        )
        parts.append(
            f'<text class="label" x="{panel_x + 18}" y="{panel_y + 22}" font-size="20" font-weight="700">{dataset_label}</text>'
        )

        def scale_x(step_index: int) -> float:
            if max_steps <= 1:
                return plot_left + plot_width / 2
            return plot_left + ((step_index - 1) / (max_steps - 1)) * plot_width

        def scale_y(score: float) -> float:
            return plot_top + (max_score - score) / (max_score - min_score) * plot_height

        for tick in range(5):
            ratio = tick / 4
            score = max_score - ratio * (max_score - min_score)
            y = plot_top + ratio * plot_height
            parts.append(f'<line class="grid" x1="{plot_left}" y1="{y:.1f}" x2="{plot_left + plot_width}" y2="{y:.1f}"/>')
            parts.append(
                f'<text class="subtle" x="{plot_left - 10:.1f}" y="{y + 5:.1f}" text-anchor="end" font-size="13">{score:.3f}</text>'
            )

        for tick in range(5):
            step = 1 if max_steps <= 1 else 1 + round((max_steps - 1) * tick / 4)
            x = scale_x(step)
            parts.append(f'<line class="grid" x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_top + plot_height}"/>')
            parts.append(
                f'<text class="subtle" x="{x:.1f}" y="{plot_top + plot_height + 22:.1f}" text-anchor="middle" font-size="13">{step}</text>'
            )

        parts.append(f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_top + plot_height}" stroke="{TEXT}" stroke-width="1.2"/>')
        parts.append(
            f'<line x1="{plot_left}" y1="{plot_top + plot_height}" x2="{plot_left + plot_width}" y2="{plot_top + plot_height}" stroke="{TEXT}" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text class="subtle" x="{plot_left + plot_width / 2:.1f}" y="{plot_top + plot_height + 46:.1f}" text-anchor="middle" font-size="14">Evaluation index within comparison group</text>'
        )

        for row in series:
            for step_index, score in row.scatter_points:
                parts.append(
                    f'<circle cx="{scale_x(step_index):.2f}" cy="{scale_y(score):.2f}" r="2.8" fill="{row.color}" opacity="0.28"/>'
                )
            polyline = " ".join(
                f"{scale_x(step_index):.2f},{scale_y(score):.2f}"
                for step_index, score in enumerate(row.best_so_far, start=1)
            )
            parts.append(f'<polyline fill="none" stroke="{row.color}" stroke-width="3.2" points="{polyline}"/>')

    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _write_summary_json(
    out_path: Path,
    q1_summaries: dict[str, dict[str, GroupSeries]],
    q2_summaries: dict[str, dict[str, GroupSeries]],
) -> None:
    payload: dict[str, object] = {"question1": {}, "question2": {}}
    for section_name, groups, summaries in (
        ("question1", Q1_GROUPS, q1_summaries),
        ("question2", Q2_GROUPS, q2_summaries),
    ):
        section_payload: dict[str, object] = {}
        for dataset_key, dataset_label, _ in DATASETS:
            section_payload[dataset_key] = {
                "label": dataset_label,
                "groups": {
                    group_key: {
                        "label": groups[group_key]["label"],
                        "best_validation": summaries[dataset_key][group_key].cell.best_validation,
                        "winner_text": summaries[dataset_key][group_key].cell.winner_text,
                        "winner_conditions": list(summaries[dataset_key][group_key].cell.conditions),
                    }
                    for group_key in groups.keys()
                },
            }
        payload[section_name] = section_payload
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    q1_summaries = _summaries_for_groups(Q1_GROUPS)
    q2_summaries = _summaries_for_groups(Q2_GROUPS)

    _build_table_svg(
        ASSET_DIR / "question1_comparison_table.svg",
        title="Question 1: Comparison Groups x Datasets",
        subtitle="Cell value is the best validation reached by that comparison group on the dataset.",
        groups=Q1_GROUPS,
        summaries=q1_summaries,
    )
    _build_table_svg(
        ASSET_DIR / "question2_comparison_table.svg",
        title="Question 2: Harness x Datasets",
        subtitle="Each cell summarizes the best validation reached by that harness family.",
        groups=Q2_GROUPS,
        summaries=q2_summaries,
    )
    _build_history_panel_svg(
        ASSET_DIR / "question1_history_panel_a.svg",
        title="Question 1: Best-Val History",
        subtitle="Line is cumulative best validation inside each comparison group. Scatter marks evaluations that did not move the frontier.",
        groups=Q1_GROUPS,
        summaries=q1_summaries,
        dataset_keys=("fashion_mnist", "twenty_newsgroups"),
    )
    _build_history_panel_svg(
        ASSET_DIR / "question1_history_panel_b.svg",
        title="Question 1: Best-Val History",
        subtitle="Line is cumulative best validation inside each comparison group. Scatter marks evaluations that did not move the frontier.",
        groups=Q1_GROUPS,
        summaries=q1_summaries,
        dataset_keys=("sms_spam", "cifar10"),
    )
    _build_history_panel_svg(
        ASSET_DIR / "question2_history_panel_a.svg",
        title="Question 2: Best-Val History",
        subtitle="Line is cumulative best validation inside each harness family. Scatter marks evaluations that did not move the frontier.",
        groups=Q2_GROUPS,
        summaries=q2_summaries,
        dataset_keys=("fashion_mnist", "twenty_newsgroups"),
    )
    _build_history_panel_svg(
        ASSET_DIR / "question2_history_panel_b.svg",
        title="Question 2: Best-Val History",
        subtitle="Line is cumulative best validation inside each harness family. Scatter marks evaluations that did not move the frontier.",
        groups=Q2_GROUPS,
        summaries=q2_summaries,
        dataset_keys=("sms_spam", "cifar10"),
    )
    _write_summary_json(
        ASSET_DIR / "cross_dataset_experiment_summary.json",
        q1_summaries=q1_summaries,
        q2_summaries=q2_summaries,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
