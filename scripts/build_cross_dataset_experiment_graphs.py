from __future__ import annotations

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

PROFILE_ORDER = ("ratchet", "screening", "advanced", "direct")
PROFILE_LABELS = {
    "ratchet": "Ratchet",
    "screening": "Screening",
    "advanced": "Advanced",
    "direct": "Direct",
}

VAL_COLOR = "#2f6fed"
HIDDEN_COLOR = "#e4572e"
TEXT = "#1f2328"
SUBTLE = "#5b6470"
GRID = "#e8ebf0"
BG = "#fffdf8"


@dataclass(frozen=True)
class FinalizedResult:
    agent_name: str
    validation_score: float
    test_score: float


@dataclass(frozen=True)
class DatasetSummary:
    key: str
    label: str
    best_val: FinalizedResult
    best_hidden: FinalizedResult
    best_val_ties: tuple[FinalizedResult, ...]
    best_hidden_ties: tuple[FinalizedResult, ...]
    profile_best_hidden: dict[str, FinalizedResult]


def _load_finalized_results(root: Path) -> list[FinalizedResult]:
    files = sorted(root.glob("*/.work/finalized/*.json"))
    if not files:
        raise FileNotFoundError(f"no finalized artifacts found under {root}")
    rows: list[FinalizedResult] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        best = payload["best_result"]
        rows.append(
            FinalizedResult(
                agent_name=str(payload["agent_name"]),
                validation_score=float(best["validation_score"]),
                test_score=float(best["test_score"]),
            )
        )
    return rows


def _profile_of(agent_name: str) -> str:
    if agent_name.startswith("ratchet_"):
        return "ratchet"
    if agent_name.startswith("screening_"):
        return "screening"
    if agent_name.startswith("advanced_"):
        return "advanced"
    return "direct"


def _short_label(agent_name: str) -> str:
    mapping = {
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
    return mapping.get(agent_name, agent_name)


def _best_by(rows: list[FinalizedResult], score_key: str) -> FinalizedResult:
    if score_key == "validation":
        return max(rows, key=lambda row: (row.validation_score, row.test_score, row.agent_name))
    return max(rows, key=lambda row: (row.test_score, row.validation_score, row.agent_name))


def _ties_for(rows: list[FinalizedResult], score_key: str) -> tuple[FinalizedResult, ...]:
    if score_key == "validation":
        top = max(row.validation_score for row in rows)
        tied = [row for row in rows if row.validation_score == top]
    else:
        top = max(row.test_score for row in rows)
        tied = [row for row in rows if row.test_score == top]
    return tuple(sorted(tied, key=lambda row: row.agent_name))


def _winner_text(rows: tuple[FinalizedResult, ...]) -> str:
    if len(rows) == 1:
        return _short_label(rows[0].agent_name)
    return f"tie x{len(rows)}"


def _summaries() -> list[DatasetSummary]:
    rows: list[DatasetSummary] = []
    for key, label, root in DATASETS:
        finalized = _load_finalized_results(root)
        profile_best: dict[str, FinalizedResult] = {}
        for profile in PROFILE_ORDER:
            profile_rows = [row for row in finalized if _profile_of(row.agent_name) == profile]
            profile_best[profile] = _best_by(profile_rows, "hidden")
        rows.append(
            DatasetSummary(
                key=key,
                label=label,
                best_val=_best_by(finalized, "validation"),
                best_hidden=_best_by(finalized, "hidden"),
                best_val_ties=_ties_for(finalized, "validation"),
                best_hidden_ties=_ties_for(finalized, "hidden"),
                profile_best_hidden=profile_best,
            )
        )
    return rows


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


def _build_winner_chart(summaries: list[DatasetSummary], out_path: Path) -> None:
    width = 1460
    height = 820
    margin_left = 78
    margin_right = 56
    margin_top = 96
    margin_bottom = 150
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    baseline_y = margin_top + plot_height
    max_score = 1.0

    def scale_y(score: float) -> float:
        return margin_top + (max_score - score) / max_score * plot_height

    def dataset_center(index: int) -> float:
        step = plot_width / len(summaries)
        return margin_left + step * index + step / 2

    bar_width = min(92, plot_width / (len(summaries) * 3.2))
    gap = 28

    parts = _svg_header(
        width,
        height,
        title="Experiment 1: Dataset Winners",
        subtitle="Best validation vs best hidden among 14 isolated conditions per dataset.",
    )

    for tick in range(6):
        score = tick / 5
        y = scale_y(score)
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}"/>')
        parts.append(
            f'<text class="subtle" x="{margin_left - 10}" y="{y + 5:.1f}" text-anchor="end" font-size="15">{score:.1f}</text>'
        )

    parts.append(f'<line x1="{margin_left}" y1="{baseline_y}" x2="{margin_left + plot_width}" y2="{baseline_y}" stroke="{TEXT}" stroke-width="1.5"/>')

    for index, summary in enumerate(summaries):
        center = dataset_center(index)
        val_x = center - bar_width - gap / 2
        hidden_x = center + gap / 2
        val_y = scale_y(summary.best_val.validation_score)
        hidden_y = scale_y(summary.best_hidden.test_score)
        val_height = baseline_y - val_y
        hidden_height = baseline_y - hidden_y

        parts.append(
            f'<rect x="{val_x:.1f}" y="{val_y:.1f}" width="{bar_width:.1f}" height="{val_height:.1f}" rx="12" fill="{VAL_COLOR}"/>'
        )
        parts.append(
            f'<rect x="{hidden_x:.1f}" y="{hidden_y:.1f}" width="{bar_width:.1f}" height="{hidden_height:.1f}" rx="12" fill="{HIDDEN_COLOR}"/>'
        )

        parts.append(
            f'<text class="label" x="{val_x + bar_width / 2:.1f}" y="{val_y - 10:.1f}" text-anchor="middle" font-size="18" font-weight="700">{summary.best_val.validation_score:.3f}</text>'
        )
        parts.append(
            f'<text class="label" x="{hidden_x + bar_width / 2:.1f}" y="{hidden_y - 10:.1f}" text-anchor="middle" font-size="18" font-weight="700">{summary.best_hidden.test_score:.3f}</text>'
        )

        parts.append(
            f'<text class="subtle" x="{val_x + bar_width / 2:.1f}" y="{baseline_y + 24:.1f}" text-anchor="middle" font-size="14">best val</text>'
        )
        parts.append(
            f'<text class="subtle" x="{hidden_x + bar_width / 2:.1f}" y="{baseline_y + 24:.1f}" text-anchor="middle" font-size="14">best hidden</text>'
        )
        parts.append(
            f'<text class="subtle" x="{val_x + bar_width / 2:.1f}" y="{baseline_y + 44:.1f}" text-anchor="middle" font-size="13">{_winner_text(summary.best_val_ties)}</text>'
        )
        parts.append(
            f'<text class="subtle" x="{hidden_x + bar_width / 2:.1f}" y="{baseline_y + 44:.1f}" text-anchor="middle" font-size="13">{_winner_text(summary.best_hidden_ties)}</text>'
        )
        parts.append(
            f'<text class="label" x="{center:.1f}" y="{baseline_y + 78:.1f}" text-anchor="middle" font-size="18" font-weight="700">{summary.label}</text>'
        )

    legend_y = height - 28
    parts.append(f'<rect x="{margin_left}" y="{legend_y - 12}" width="22" height="12" rx="4" fill="{VAL_COLOR}"/>')
    parts.append(f'<text class="subtle" x="{margin_left + 30}" y="{legend_y - 1}" font-size="14">Best validation found in the run history</text>')
    parts.append(f'<rect x="{margin_left + 360}" y="{legend_y - 12}" width="22" height="12" rx="4" fill="{HIDDEN_COLOR}"/>')
    parts.append(f'<text class="subtle" x="{margin_left + 390}" y="{legend_y - 1}" font-size="14">Best hidden-test score after finalize</text>')
    parts.append(f'<text class="subtle" x="{margin_left + 790}" y="{legend_y - 1}" font-size="14">labels show winner name or tie count</text>')
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _mix_color(low: str, high: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    low_rgb = tuple(int(low[index : index + 2], 16) for index in (1, 3, 5))
    high_rgb = tuple(int(high[index : index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(int(round(lo + (hi - lo) * ratio)) for lo, hi in zip(low_rgb, high_rgb))
    return "#" + "".join(f"{value:02x}" for value in mixed)


def _build_profile_heatmap(summaries: list[DatasetSummary], out_path: Path) -> None:
    width = 1460
    height = 760
    margin_left = 180
    margin_right = 120
    margin_top = 118
    margin_bottom = 76
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    cell_width = plot_width / len(PROFILE_ORDER)
    cell_height = plot_height / len(summaries)
    gap_floor = -0.03
    best_fill = "#1d8f6a"
    weak_fill = "#f4e6cf"

    parts = _svg_header(
        width,
        height,
        title="Experiment 2: Hidden-Test Gap By Harness Profile",
        subtitle="Cell fill is the gap to the row-best hidden score. Text is the best hidden score reached by that profile.",
    )

    for col_index, profile in enumerate(PROFILE_ORDER):
        x = margin_left + col_index * cell_width + cell_width / 2
        parts.append(
            f'<text class="label" x="{x:.1f}" y="{margin_top - 24:.1f}" text-anchor="middle" font-size="19" font-weight="700">{PROFILE_LABELS[profile]}</text>'
        )

    for row_index, summary in enumerate(summaries):
        y_top = margin_top + row_index * cell_height
        y_center = y_top + cell_height / 2
        row_best = max(item.test_score for item in summary.profile_best_hidden.values())
        parts.append(
            f'<text class="label" x="{margin_left - 18:.1f}" y="{y_center + 6:.1f}" text-anchor="end" font-size="18" font-weight="700">{summary.label}</text>'
        )
        for col_index, profile in enumerate(PROFILE_ORDER):
            x = margin_left + col_index * cell_width
            result = summary.profile_best_hidden[profile]
            gap = result.test_score - row_best
            ratio = (gap - gap_floor) / (0 - gap_floor)
            fill = _mix_color(weak_fill, best_fill, ratio)
            parts.append(
                f'<rect x="{x + 8:.1f}" y="{y_top + 8:.1f}" width="{cell_width - 16:.1f}" height="{cell_height - 16:.1f}" rx="18" fill="{fill}" stroke="#d7dce3" stroke-width="1"/>'
            )
            text_fill = "#ffffff" if ratio > 0.65 else TEXT
            subtle_fill = "#eef8f4" if ratio > 0.65 else SUBTLE
            parts.append(
                f'<text x="{x + cell_width / 2:.1f}" y="{y_top + cell_height / 2 - 6:.1f}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="24" font-weight="700" fill="{text_fill}">{result.test_score:.3f}</text>'
            )
            parts.append(
                f'<text x="{x + cell_width / 2:.1f}" y="{y_top + cell_height / 2 + 18:.1f}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="14" fill="{subtle_fill}">{_short_label(result.agent_name)}</text>'
            )
            parts.append(
                f'<text x="{x + cell_width / 2:.1f}" y="{y_top + cell_height - 18:.1f}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="13" fill="{subtle_fill}">{gap:+.3f} vs row best</text>'
            )

    legend_x = margin_left
    legend_y = height - 28
    for index, ratio in enumerate((0.0, 0.33, 0.66, 1.0)):
        fill = _mix_color(weak_fill, best_fill, ratio)
        x = legend_x + index * 68
        parts.append(f'<rect x="{x:.1f}" y="{legend_y - 14:.1f}" width="52" height="14" rx="4" fill="{fill}" stroke="#d7dce3" stroke-width="0.8"/>')
    parts.append(f'<text class="subtle" x="{legend_x + 288:.1f}" y="{legend_y - 2:.1f}" font-size="14">lighter = farther from the dataset-best hidden score</text>')
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _write_summary_json(summaries: list[DatasetSummary], out_path: Path) -> None:
    payload = []
    for summary in summaries:
        payload.append(
            {
                "dataset": summary.key,
                "label": summary.label,
                "best_val": {
                    "agent_name": summary.best_val.agent_name,
                    "validation_score": summary.best_val.validation_score,
                    "test_score": summary.best_val.test_score,
                    "ties": [row.agent_name for row in summary.best_val_ties],
                },
                "best_hidden": {
                    "agent_name": summary.best_hidden.agent_name,
                    "validation_score": summary.best_hidden.validation_score,
                    "test_score": summary.best_hidden.test_score,
                    "ties": [row.agent_name for row in summary.best_hidden_ties],
                },
                "profile_best_hidden": {
                    profile: {
                        "agent_name": result.agent_name,
                        "validation_score": result.validation_score,
                        "test_score": result.test_score,
                    }
                    for profile, result in summary.profile_best_hidden.items()
                },
            }
        )
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    summaries = _summaries()
    _build_winner_chart(summaries, ASSET_DIR / "cross_dataset_winners.svg")
    _build_profile_heatmap(summaries, ASSET_DIR / "profile_hidden_gap_heatmap.svg")
    _write_summary_json(summaries, ASSET_DIR / "cross_dataset_experiment_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
