from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from autoresearch.runtime_paths import report_path


REPORT_LABELS = (
    "Anchor",
    "Question",
    "Alias risk",
    "Prediction",
    "Belief",
    "Next",
    "Hypothesis",
    "Change",
    "Why",
    "Interpretation",
    "Expected signal",
    "Stage",
    "Factors",
    "Levels",
    "Design",
    "Target effect or interaction",
    "Observed signal",
    "Decision",
    "Verdict",
    "Review",
)

_RUN_HEADING_PATTERN = re.compile(r"^##\s+Run\s+(?:`([^`]+)`|(\S+))\s*$")

_REPORT_TEMPLATE = """# Report

Append one section per completed run using this shape:

## Run `<run_id>`
Hypothesis: ...
Interpretation: ...
Decision: ...
Next: ...

Freeform analysis is allowed below the labeled lines when needed.
"""


@dataclass(frozen=True)
class ReportEntry:
    run_id: str
    text: str
    fields: dict[str, str]


def parse_report_fields(report_text: str) -> dict[str, str]:
    report_text = " ".join(report_text.split())
    if not report_text:
        return {}

    fields: dict[str, str] = {}
    positions: list[tuple[int, str]] = []
    for label in REPORT_LABELS:
        marker = f"{label}:"
        start = report_text.find(marker)
        if start >= 0:
            positions.append((start, label))
    positions.sort()

    if not positions:
        return {"Review": report_text}

    for index, (start, label) in enumerate(positions):
        marker = f"{label}:"
        value_start = start + len(marker)
        value_end = positions[index + 1][0] if index + 1 < len(positions) else len(report_text)
        value = report_text[value_start:value_end].strip()
        if value:
            fields[label] = value
    return fields


def _render_default_report() -> str:
    return _REPORT_TEMPLATE.rstrip() + "\n"


def ensure_report_file(root: Path, agent_name_or_dir: str | Path) -> Path:
    target_path = report_path(root, agent_name_or_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        target_path.write_text(_render_default_report(), encoding="utf-8")
    return target_path


def append_report_entry(root: Path, agent_name_or_dir: str | Path, run_id: str, report_text: str) -> Path:
    target_path = ensure_report_file(root, agent_name_or_dir)
    existing = target_path.read_text(encoding="utf-8").rstrip()
    entry_body = report_text.strip()
    entry = f"## Run `{run_id}`\n"
    if entry_body:
        entry += f"{entry_body}\n"
    if existing:
        updated = f"{existing}\n\n{entry}"
    else:
        updated = entry
    target_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return target_path


def load_report_entries(path: Path) -> dict[str, ReportEntry]:
    if not path.exists():
        return {}

    entries: dict[str, ReportEntry] = {}
    current_run_id: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_run_id, buffer
        if current_run_id is None:
            buffer = []
            return
        text = "\n".join(buffer).strip()
        entries[current_run_id] = ReportEntry(
            run_id=current_run_id,
            text=text,
            fields=parse_report_fields(text),
        )
        buffer = []

    for line in path.read_text(encoding="utf-8").splitlines():
        match = _RUN_HEADING_PATTERN.match(line.strip())
        if match:
            flush()
            current_run_id = match.group(1) or match.group(2)
            buffer = []
            continue
        if current_run_id is not None:
            buffer.append(line)
    flush()
    return entries
