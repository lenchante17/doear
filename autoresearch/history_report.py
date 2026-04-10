from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json

from autoresearch.agent_report import load_report_entries
from autoresearch.runtime_paths import history_path, report_path


@dataclass(frozen=True)
class HistoryRow:
    run_id: str
    benchmark: str
    dataset: str
    candidate: str
    model: str
    validation_score: float
    rank: int
    backend: str
    mode: str
    advisors: str
    selection_origin: str
    advice: str
    artifact: str


@dataclass(frozen=True)
class AgentRound:
    round_index: int
    run_id: str
    benchmark: str
    dataset: str
    model: str
    best_candidate: str
    best_validation_score: float
    backend: str
    mode: str
    advisors: str
    selection_origin: str
    artifact: str
    report_text: str
    report_fields: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "run_id": self.run_id,
            "benchmark": self.benchmark,
            "dataset": self.dataset,
            "model": self.model,
            "best_candidate": self.best_candidate,
            "best_validation_score": self.best_validation_score,
            "backend": self.backend,
            "mode": self.mode,
            "advisors": self.advisors,
            "selection_origin": self.selection_origin,
            "artifact": self.artifact,
            "report_text": self.report_text,
            "report_fields": dict(self.report_fields),
        }


@dataclass(frozen=True)
class AgentComparison:
    agent_name: str
    history_path: str
    report_path: str
    rounds: tuple[AgentRound, ...]

    @property
    def start_validation_score(self) -> float:
        return self.rounds[0].best_validation_score

    @property
    def best_validation_score(self) -> float:
        return max(round_.best_validation_score for round_ in self.rounds)

    @property
    def final_validation_score(self) -> float:
        return self.rounds[-1].best_validation_score

    @property
    def improvement(self) -> float:
        return self.final_validation_score - self.start_validation_score

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "history_path": self.history_path,
            "report_path": self.report_path,
            "start_validation_score": self.start_validation_score,
            "best_validation_score": self.best_validation_score,
            "final_validation_score": self.final_validation_score,
            "improvement": self.improvement,
            "rounds": [round_.to_dict() for round_ in self.rounds],
        }


@dataclass(frozen=True)
class ComparisonReport:
    title: str
    benchmark: str
    model: str
    generated_at: str
    agents: tuple[AgentComparison, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "benchmark": self.benchmark,
            "model": self.model,
            "generated_at": self.generated_at,
            "agents": [agent.to_dict() for agent in self.agents],
        }


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise ValueError(f"Expected a markdown table row, got: {line!r}")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def load_history_rows(history_path: Path) -> list[HistoryRow]:
    lines = history_path.read_text(encoding="utf-8").splitlines()
    table_start = None
    for index, line in enumerate(lines):
        if line.strip().startswith("| run_id |"):
            table_start = index
            break
    if table_start is None or table_start + 1 >= len(lines):
        raise ValueError(f"History table not found in {history_path}")

    headers = _split_markdown_row(lines[table_start])
    rows: list[HistoryRow] = []
    for line in lines[table_start + 2 :]:
        if not line.strip().startswith("|"):
            continue
        values = _split_markdown_row(line)
        if len(values) != len(headers):
            raise ValueError(f"Malformed history row in {history_path}: {line!r}")
        record = dict(zip(headers, values))
        rows.append(
            HistoryRow(
                run_id=record["run_id"],
                benchmark=record["benchmark"],
                dataset=record["dataset"],
                candidate=record["candidate"],
                model=record["model"],
                validation_score=float(record["validation_score"]),
                rank=int(record["rank"]),
                backend=record["backend"],
                mode=record.get("mode", "agent"),
                advisors=record.get("advisors", "-"),
                selection_origin=record.get("selection_origin", "manual_submission"),
                advice=record.get("advice", "-"),
                artifact=record["artifact"].strip("`"),
            )
        )
    return rows


def build_agent_rounds(
    history_path: Path,
    report_path: Path,
    benchmark_id: str,
    model_family: str,
) -> tuple[AgentRound, ...]:
    report_entries = load_report_entries(report_path)
    filtered_rows = [
        row
        for row in load_history_rows(history_path)
        if row.benchmark == benchmark_id and row.model == model_family
    ]
    grouped: dict[str, list[HistoryRow]] = {}
    ordered_run_ids: list[str] = []
    for row in filtered_rows:
        if row.run_id not in grouped:
            grouped[row.run_id] = []
            ordered_run_ids.append(row.run_id)
        grouped[row.run_id].append(row)

    rounds: list[AgentRound] = []
    for round_index, run_id in enumerate(ordered_run_ids, start=1):
        run_rows = grouped[run_id]
        best_row = min(run_rows, key=lambda row: (row.rank, -row.validation_score, row.candidate))
        report_entry = report_entries.get(run_id)
        report_text = report_entry.text if report_entry is not None else ""
        report_fields = report_entry.fields if report_entry is not None else {}
        rounds.append(
            AgentRound(
                round_index=round_index,
                run_id=run_id,
                benchmark=best_row.benchmark,
                dataset=best_row.dataset,
                model=best_row.model,
                best_candidate=best_row.candidate,
                best_validation_score=max(row.validation_score for row in run_rows),
                backend=best_row.backend,
                mode=best_row.mode,
                advisors=best_row.advisors,
                selection_origin=best_row.selection_origin,
                artifact=best_row.artifact,
                report_text=report_text,
                report_fields=report_fields,
            )
        )

    return tuple(rounds)


def build_comparison_report(
    root: Path,
    agent_dirs: list[Path],
    benchmark_id: str,
    model_family: str,
    title: str | None = None,
) -> ComparisonReport:
    root = root.resolve()
    agents: list[AgentComparison] = []
    for agent_dir in agent_dirs:
        agent_history_path = history_path(root, agent_dir).resolve()
        agent_report_path = report_path(root, agent_dir).resolve()
        rounds = build_agent_rounds(
            agent_history_path,
            agent_report_path,
            benchmark_id=benchmark_id,
            model_family=model_family,
        )
        if not rounds:
            continue
        try:
            history_label = str(agent_history_path.relative_to(root))
        except ValueError:
            history_label = str(agent_history_path)
        try:
            report_label = str(agent_report_path.relative_to(root))
        except ValueError:
            report_label = str(agent_report_path)
        agents.append(
            AgentComparison(
                agent_name=agent_dir.name,
                history_path=history_label,
                report_path=report_label,
                rounds=rounds,
            )
        )

    if not agents:
        raise ValueError(
            f"No history rows matched benchmark={benchmark_id!r} model={model_family!r} for the selected agents."
        )

    return ComparisonReport(
        title=title or f"History comparison: {benchmark_id} / {model_family}",
        benchmark=benchmark_id,
        model=model_family,
        generated_at=datetime.now(timezone.utc).isoformat(),
        agents=tuple(agents),
    )


def _format_score(value: float) -> str:
    return f"{value:.6f}"


def _build_chart(report: ComparisonReport) -> str:
    width = 960
    height = 360
    margin_left = 60
    margin_right = 220
    margin_top = 20
    margin_bottom = 40
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    colors = (
        "#1768AC",
        "#D7263D",
        "#1B998B",
        "#F4A259",
        "#5C4D7D",
        "#2E294E",
    )

    scores = [
        round_.best_validation_score
        for agent in report.agents
        for round_ in agent.rounds
    ]
    min_score = min(scores)
    max_score = max(scores)
    if min_score == max_score:
        min_score -= 0.01
        max_score += 0.01
    else:
        padding = (max_score - min_score) * 0.1
        min_score -= padding
        max_score += padding

    max_rounds = max(len(agent.rounds) for agent in report.agents)

    def scale_x(round_index: int) -> float:
        if max_rounds == 1:
            return margin_left + (plot_width / 2)
        return margin_left + ((round_index - 1) / (max_rounds - 1)) * plot_width

    def scale_y(score: float) -> float:
        return margin_top + (max_score - score) / (max_score - min_score) * plot_height

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Validation score by round">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="white" />',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#333" />',
        f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#333" />',
    ]

    tick_count = 5
    for tick in range(tick_count):
        ratio = tick / (tick_count - 1)
        score = max_score - ratio * (max_score - min_score)
        y = margin_top + ratio * plot_height
        parts.append(
            f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" y2="{y:.2f}" stroke="#E5E7EB" />'
        )
        parts.append(
            f'<text x="{margin_left - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#444">{_format_score(score)}</text>'
        )

    for round_index in range(1, max_rounds + 1):
        x = scale_x(round_index)
        parts.append(
            f'<line x1="{x:.2f}" y1="{margin_top}" x2="{x:.2f}" y2="{margin_top + plot_height}" stroke="#F3F4F6" />'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{margin_top + plot_height + 20}" text-anchor="middle" font-size="11" fill="#444">{round_index}</text>'
        )

    for index, agent in enumerate(report.agents):
        color = colors[index % len(colors)]
        point_pairs = [
            f"{scale_x(round_.round_index):.2f},{scale_y(round_.best_validation_score):.2f}"
            for round_ in agent.rounds
        ]
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{" ".join(point_pairs)}" />'
        )
        for round_ in agent.rounds:
            x = scale_x(round_.round_index)
            y = scale_y(round_.best_validation_score)
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"><title>{escape(agent.agent_name)} round {round_.round_index}: {_format_score(round_.best_validation_score)}</title></circle>'
            )

    legend_x = margin_left + plot_width + 24
    legend_y = margin_top + 22
    for index, agent in enumerate(report.agents):
        color = colors[index % len(colors)]
        y = legend_y + index * 22
        parts.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 18}" y2="{y}" stroke="{color}" stroke-width="3" />')
        parts.append(
            f'<text x="{legend_x + 26}" y="{y + 4}" font-size="12" fill="#222">{escape(agent.agent_name)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _key_judgment(fields: dict[str, str], report_text: str) -> str:
    for label in ("Decision", "Interpretation", "Change", "Hypothesis", "Review"):
        value = fields.get(label)
        if value:
            return value
    return report_text


def render_report_html(report: ComparisonReport) -> str:
    summary_rows = []
    for agent in report.agents:
        summary_rows.append(
            "<tr>"
            f"<td>{escape(agent.agent_name)}</td>"
            f"<td>{len(agent.rounds)}</td>"
            f"<td>{_format_score(agent.start_validation_score)}</td>"
            f"<td>{_format_score(agent.best_validation_score)}</td>"
            f"<td>{_format_score(agent.final_validation_score)}</td>"
            f"<td>{_format_score(agent.improvement)}</td>"
            "</tr>"
        )

    judgment_rows = []
    for round_index in range(1, max(len(agent.rounds) for agent in report.agents) + 1):
        for agent in report.agents:
            if round_index > len(agent.rounds):
                continue
            round_ = agent.rounds[round_index - 1]
            judgment_rows.append(
                "<tr>"
                f"<td>{round_.round_index}</td>"
                f"<td>{escape(agent.agent_name)}</td>"
                f"<td>{escape(round_.best_candidate)}</td>"
                f"<td>{_format_score(round_.best_validation_score)}</td>"
                f"<td>{escape(round_.report_fields.get('Stage', ''))}</td>"
                f"<td>{escape(_key_judgment(round_.report_fields, round_.report_text))}</td>"
                f"<td>{escape(round_.report_text)}</td>"
                "</tr>"
            )

    chart = _build_chart(report)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{escape(report.title)}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 24px;
      color: #111827;
      background: #F9FAFB;
    }}
    h1, h2 {{
      margin: 0 0 12px 0;
    }}
    p {{
      margin: 6px 0 16px 0;
    }}
    .panel {{
      background: white;
      border: 1px solid #E5E7EB;
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid #E5E7EB;
      padding: 8px 10px;
      vertical-align: top;
    }}
    th {{
      background: #F3F4F6;
    }}
    .meta {{
      color: #4B5563;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <div class="panel">
    <h1>{escape(report.title)}</h1>
    <p class="meta">Benchmark: <strong>{escape(report.benchmark)}</strong> | Model: <strong>{escape(report.model)}</strong> | Generated: <strong>{escape(report.generated_at)}</strong></p>
  </div>

  <div class="panel">
    <h2>Validation Trajectory</h2>
    {chart}
  </div>

  <div class="panel">
    <h2>Agent Summary</h2>
    <table>
      <thead>
        <tr>
          <th>Agent</th>
          <th>Rounds</th>
          <th>Start</th>
          <th>Best</th>
          <th>Final</th>
          <th>Delta</th>
        </tr>
      </thead>
      <tbody>
        {''.join(summary_rows)}
      </tbody>
    </table>
  </div>

  <div class="panel">
    <h2>Judgment Timeline</h2>
    <table>
      <thead>
        <tr>
          <th>Round</th>
          <th>Agent</th>
          <th>Best Candidate</th>
          <th>Score</th>
          <th>Stage</th>
          <th>Key Judgment</th>
          <th>Full Report</th>
        </tr>
      </thead>
      <tbody>
        {''.join(judgment_rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def write_comparison_report(report: ComparisonReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "index.html"
    json_path = output_dir / "report.json"
    html_path.write_text(render_report_html(report), encoding="utf-8")
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return html_path, json_path


def resolve_agent_dirs(
    root: Path,
    agent_paths: list[str] | None = None,
    agent_globs: list[str] | None = None,
    agents_dir: str = "agents",
) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    agent_root = root / agents_dir

    for agent_path in agent_paths or []:
        candidate = Path(agent_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if candidate not in seen:
            resolved.append(candidate)
            seen.add(candidate)

    for pattern in agent_globs or []:
        for match in sorted(agent_root.glob(pattern)):
            candidate = match.resolve()
            if candidate.is_dir() and candidate not in seen:
                resolved.append(candidate)
                seen.add(candidate)

    return resolved
